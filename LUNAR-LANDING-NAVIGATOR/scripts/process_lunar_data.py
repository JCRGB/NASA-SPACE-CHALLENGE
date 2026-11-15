"""Ingest NASA PGDA lunar polar DEM and illumination GeoTIFFs.

Inputs: data/raw/elevation.tif and data/raw/sunlight.tif. Elevation is the
master grid; outputs are compact point arrays in data/processed/.
"""
from __future__ import annotations
import json
import math
import warnings
from pathlib import Path
from typing import Any
import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.transform import xy
from rasterio.warp import reproject
from scipy.ndimage import distance_transform_edt

MOON_RADIUS_M = 1_737_400.0
SOLAR_CONSTANT_W_M2 = 1361.0
PANEL_EFFICIENCY = 0.20
MAX_OUTPUT_SIDE = 150
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
ELEVATION_PATH = RAW_DIR / "Site04_final_adj_5mpp_surf.tif"
SUNLIGHT_PATH = RAW_DIR / "sunlight.tif"

def read_scaled_band(src: rasterio.io.DatasetReader, band: int = 1) -> np.ndarray:
    """Read band as float, apply GDAL scale/offset, and replace nodata with NaN."""
    masked = src.read(band, masked=True).astype(np.float64)
    raw = np.asarray(masked.data, dtype=np.float64)
    invalid = np.ma.getmaskarray(masked) | ~np.isfinite(raw)
    if src.nodata is not None:
        invalid |= np.isclose(raw, src.nodata, rtol=0.0, atol=1e-8)
    invalid |= (raw == -32768.0) | (np.abs(raw) > 1e20)
    scales, offsets = src.scales or (1.0,), src.offsets or (0.0,)
    scale = float(scales[band - 1]) if len(scales) >= band else 1.0
    offset = float(offsets[band - 1]) if len(offsets) >= band else 0.0
    values = raw * scale + offset
    values[invalid] = np.nan
    return values

def normalize_elevation(data: np.ndarray, units: str | None) -> np.ndarray:
    """Convert kilometres/radius values to metres above lunar datum."""
    out = np.asarray(data, dtype=np.float64).copy()
    if (units or "").strip().lower() in {"km", "kilometer", "kilometers", "kilometre", "kilometres"}:
        out *= 1000.0
    if np.isfinite(out).any() and float(np.nanmedian(out)) > 1_000_000.0:
        out -= MOON_RADIUS_M
    return out

def normalize_sunlight_percent(data: np.ndarray) -> np.ndarray:
    """Normalize fraction, percent, and integer-encoded illumination to 0-100%."""
    out = np.asarray(data, dtype=np.float64).copy()
    if not np.isfinite(out).any():
        return out
    low, high = float(np.nanmin(out)), float(np.nanmax(out))
    if low >= 0.0 and high <= 1.5:
        out *= 100.0
    elif high > 100.0 and low >= 0.0:
        # Handles unscaled byte/packed-percent products (e.g. 0-255 or 0-10000).
        out *= 100.0 / high
    elif low < 0.0 or high > 100.0:
        warnings.warn("Sunlight values outside expected percentage range; clipping")
    return np.clip(out, 0.0, 100.0)

def align_sunlight(sun: np.ndarray, sun_transform: rasterio.Affine, sun_crs: Any,
                   shape: tuple[int, int], transform: rasterio.Affine, crs: Any) -> np.ndarray:
    """Warp sunlight onto the exact elevation grid using bilinear resampling."""
    if sun_crs is None or crs is None:
        raise ValueError("Both GeoTIFFs must contain a CRS")
    aligned = np.full(shape, np.nan, dtype=np.float64)
    reproject(source=sun, destination=aligned, src_transform=sun_transform, src_crs=sun_crs,
              src_nodata=np.nan, dst_transform=transform, dst_crs=crs, dst_nodata=np.nan,
              resampling=Resampling.bilinear, init_dest_nodata=True)
    return aligned

def calculate_slope(elevation_m: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Calculate slope from projected pixel spacing in metres."""
    dem = np.asarray(elevation_m, dtype=np.float64)
    if dem.ndim != 2 or min(dem.shape) < 2:
        raise ValueError("Elevation must be a 2D grid at least 2x2")
    if dx <= 0.0 or dy <= 0.0:
        raise ValueError("Pixel resolution must be positive")
    valid = np.isfinite(dem)
    if not valid.any():
        return np.full(dem.shape, np.nan)
    filled = np.where(valid, dem, float(np.nanmedian(dem)))
    dz_dy, dz_dx = np.gradient(filled, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
    # Exclude cells adjacent to DEM nodata so fill values cannot create slopes.
    safe = valid.copy()
    safe[1:, :] &= valid[:-1, :]
    safe[:-1, :] &= valid[1:, :]
    safe[:, 1:] &= valid[:, :-1]
    safe[:, :-1] &= valid[:, 1:]
    slope[~safe] = np.nan
    return slope

def projected_xy_to_latlon(x: np.ndarray, y: np.ndarray, source_crs: Any) -> tuple[np.ndarray, np.ndarray]:
    """Convert lunar polar stereographic X/Y to lat/lon; use lunar-radius inverse as fallback."""
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    crs = CRS.from_user_input(source_crs) if source_crs is not None else None
    if crs is not None:
        try:
            radius = float(crs.ellipsoid.semi_major_metre)
        except (AttributeError, TypeError, ValueError):
            radius = math.nan
        if math.isfinite(radius) and abs(radius - MOON_RADIUS_M) / MOON_RADIUS_M < 0.01:
            lunar_geog = CRS.from_proj4(f"+proj=longlat +R={MOON_RADIUS_M} +no_defs +type=crs")
            lon, lat = Transformer.from_crs(crs, lunar_geog, always_xy=True).transform(x, y)
            return np.asarray(lat), np.asarray(lon)
    rho = np.hypot(x, y)
    lat = -90.0 + np.degrees(2.0 * np.arctan(rho / (2.0 * MOON_RADIUS_M)))
    lon = (np.degrees(np.arctan2(x, y)) + 180.0) % 360.0 - 180.0
    return lat, lon

def solar_potential(illumination_percent: np.ndarray) -> np.ndarray:
    illum = np.clip(np.asarray(illumination_percent, dtype=np.float64), 0.0, 100.0)
    value = SOLAR_CONSTANT_W_M2 * illum / 100.0 * 24.0 * PANEL_EFFICIENCY / 1000.0
    return np.where(np.isfinite(illum), value, np.nan)

def suitability_score(slope: np.ndarray, illum: np.ndarray, pixel_m: float) -> tuple[np.ndarray, np.ndarray]:
    valid = np.isfinite(slope) & np.isfinite(illum)
    terrain = np.clip(1.0 - np.maximum(slope, 0.0) / 30.0, 0.0, 1.0)
    solar = np.clip(illum, 0.0, 100.0) / 100.0
    shadow = (illum < 5.0) & valid
    ice = np.clip(1.0 - distance_transform_edt(~shadow) * pixel_m / 10_000.0, 0.0, 1.0) if shadow.any() else np.zeros_like(illum)
    score = 100.0 * (0.5 * terrain + 0.3 * solar + 0.2 * ice)
    score = np.where(slope > 15.0, score * 0.35, score)
    score = np.where(valid, np.clip(score, 0.0, 100.0), np.nan)
    risk = np.full(score.shape, "Hazardous", dtype=object)
    risk[(score >= 40.0) & (slope <= 15.0)] = "Moderate"
    risk[(score >= 70.0) & (slope <= 15.0)] = "Optimal"
    risk[~valid] = "NoData"
    return score, risk

def sample_grid(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    stride = max(1, int(math.ceil(max(shape) / MAX_OUTPUT_SIDE)))
    r, c = np.arange(0, shape[0], stride), np.arange(0, shape[1], stride)
    return np.meshgrid(r, c, indexing="ij")

def export_json(elevation: np.ndarray, sunlight: np.ndarray, slope: np.ndarray,
                solar: np.ndarray, scores: np.ndarray, risks: np.ndarray,
                transform: rasterio.Affine, crs: Any, output_dir: Path = OUT_DIR) -> int:
    """Export four filtered, downsampled JSON arrays with map coordinates."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows, cols = sample_grid(elevation.shape)
    elev, sun, slp = elevation[rows, cols], sunlight[rows, cols], slope[rows, cols]
    sol, score, risk = solar[rows, cols], scores[rows, cols], risks[rows, cols]
    valid = np.isfinite(elev) & np.isfinite(sun) & np.isfinite(slp) & np.isfinite(sol) & np.isfinite(score)
    sampled_rows, sampled_cols = rows[valid], cols[valid]
    xs, ys = xy(transform, sampled_rows, sampled_cols, offset="center")
    lat, lon = projected_xy_to_latlon(np.asarray(xs), np.asarray(ys), crs)
    in_region = np.isfinite(lat) & np.isfinite(lon) & (lat >= -90.0) & (lat <= -80.0)
    lat, lon = lat[in_region], lon[in_region]
    elev, sun, slp = elev[valid][in_region], sun[valid][in_region], slp[valid][in_region]
    sol, score, risk = sol[valid][in_region], score[valid][in_region], risk[valid][in_region]

    def records(values: np.ndarray, unit: str, extra: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        result = []
        for i, value in enumerate(values):
            item = {"lat": round(float(lat[i]), 6), "lon": round(float(lon[i]), 6),
                    "value": round(float(value), 4), "unit": unit}
            if extra is not None:
                item.update(extra[i])
            result.append(item)
        return result

    files = {
        "sunlight_data.json": records(sun, "%"),
        "slope_data.json": records(slp, "degrees", [{"elevation_m": round(float(v), 3)} for v in elev]),
        "solar_potential.json": records(sol, "kWh/m^2/day"),
        "suitability_scores.json": records(score, "score_0_100", [{"risk_rating": str(v)} for v in risk]),
    }
    for name, values in files.items():
        with (output_dir / name).open("w", encoding="utf-8") as f:
            json.dump(values, f, separators=(",", ":"), allow_nan=False)
    return len(lat)

def process_lunar_data(elevation_path: Path = ELEVATION_PATH,
                       sunlight_path: Path = SUNLIGHT_PATH,
                       output_dir: Path = OUT_DIR) -> int:
    """Load, align, calculate, summarize, and export real NASA GeoTIFF inputs."""
    if not elevation_path.is_file():
        raise FileNotFoundError(f"Missing elevation GeoTIFF: {elevation_path}")
    if not sunlight_path.is_file():
        raise FileNotFoundError(f"Missing sunlight GeoTIFF: {sunlight_path}")

    with rasterio.open(elevation_path) as dem_src:
        if dem_src.crs is None or dem_src.count < 1:
            raise ValueError("Elevation GeoTIFF needs a CRS and at least one band")
        elevation = normalize_elevation(read_scaled_band(dem_src), dem_src.units[0] if dem_src.units else None)
        transform, crs = dem_src.transform, dem_src.crs
        shape = (dem_src.height, dem_src.width)
        dx, dy = math.hypot(transform.a, transform.d), math.hypot(transform.b, transform.e)
    if dx <= 0.0 or dy <= 0.0:
        raise ValueError("Elevation GeoTIFF has invalid pixel dimensions")

    with rasterio.open(sunlight_path) as sun_src:
        if sun_src.crs is None or sun_src.count < 1:
            raise ValueError("Sunlight GeoTIFF needs a CRS and at least one band")
        sunlight = normalize_sunlight_percent(read_scaled_band(sun_src))
        sunlight = align_sunlight(sunlight, sun_src.transform, sun_src.crs, shape, transform, crs)

    overlap = np.isfinite(elevation) & np.isfinite(sunlight)
    if not overlap.any():
        raise ValueError("Elevation and sunlight rasters have no overlapping valid pixels")
    dem_for_slope = elevation.copy()
    dem_for_slope[~overlap] = np.nan
    slope = calculate_slope(dem_for_slope, dx, dy)
    solar = solar_potential(sunlight)
    scores, risks = suitability_score(slope, sunlight, math.sqrt(dx * dy))
    valid = overlap & np.isfinite(slope)
    if not valid.any():
        raise ValueError("No valid pixels remain after slope calculation")
    elevation = np.where(valid, elevation, np.nan)
    sunlight, slope = np.where(valid, sunlight, np.nan), np.where(valid, slope, np.nan)
    solar, scores = np.where(valid, solar, np.nan), np.where(valid, scores, np.nan)

    count = export_json(elevation, sunlight, slope, solar, scores, risks, transform, crs, output_dir)
    print("NASA lunar South Pole processing complete")
    print(f"  Input CRS: {crs}")
    print(f"  Elevation pixel resolution: dx={dx:.3f} m, dy={dy:.3f} m")
    print(f"  Elevation min/max: {np.nanmin(elevation):.3f} / {np.nanmax(elevation):.3f} m")
    print(f"  Slope min/max: {np.nanmin(slope):.3f} / {np.nanmax(slope):.3f} degrees")
    print(f"  Sunlight min/max: {np.nanmin(sunlight):.3f} / {np.nanmax(sunlight):.3f} %")
    print(f"  Valid points exported: {count}")
    print(f"  JSON output directory: {output_dir}")
    return count

if __name__ == "__main__":
    process_lunar_data()
27
