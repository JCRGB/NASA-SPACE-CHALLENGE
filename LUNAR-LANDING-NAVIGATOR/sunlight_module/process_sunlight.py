#!/usr/bin/env python3
"""Convert NASA polar illumination GeoTIFF pixels to a compact Three.js JSON grid."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer

HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "raw_data" / "AVGVISIB_65S_240M_201608.tiff"
DEFAULT_OUTPUT = HERE / "output" / "sunlight_data.json"
LUNAR_RADIUS_M = 1_737_400.0
DATASET = "NASA LRO LOLA Lunar Polar Illumination"
SOURCE = "NASA Planetary Geodesy Data Archive (PGDA)"


def _clean_values(src: rasterio.io.DatasetReader) -> tuple[np.ndarray, dict[str, Any]]:
    """Read band 1, apply its GeoTIFF scale/offset and mask invalid values."""
    band = src.read(1, masked=True)
    raw = np.asarray(band.data, dtype=np.float64)
    invalid = np.ma.getmaskarray(band) | ~np.isfinite(raw)
    # A common signed-integer fill value is not always declared as nodata.
    invalid |= raw == -32768
    scale = float(src.scales[0]) if src.scales else 1.0
    offset = float(src.offsets[0]) if src.offsets else 0.0
    values = raw * scale + offset
    values[invalid] = np.nan

    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("The input raster has no valid illumination pixels.")

    # NASA products are commonly stored as percent; some derivative files use
    # fractions. Infer fraction only when the entire finite range is <= 1.
    detected_encoding = "fraction" if finite.min() >= 0.0 and finite.max() <= 1.0 else "percent"
    if detected_encoding == "fraction":
        values *= 100.0
    # Reject out-of-range values rather than silently clipping corrupted data.
    values[(values < 0.0) | (values > 100.0)] = np.nan
    metadata = {
        "nodata": src.nodata,
        "scale": scale,
        "offset": offset,
        "detected_value_encoding": detected_encoding,
    }
    return values, metadata


def _sample_indices(values: np.ndarray, max_points: int, seed: int = 17) -> np.ndarray:
    """Select spatially distributed points while retaining shadow/sunlit tails."""
    valid_flat = np.flatnonzero(np.isfinite(values).ravel())
    if valid_flat.size <= max_points:
        return valid_flat

    flat_values = values.ravel()
    groups = [
        valid_flat[flat_values[valid_flat] < 5.0],
        valid_flat[(flat_values[valid_flat] >= 5.0) & (flat_values[valid_flat] <= 50.0)],
        valid_flat[flat_values[valid_flat] > 50.0],
    ]
    # Allocate points proportionally, with a floor for each non-empty class.
    weights = np.array([len(group) for group in groups], dtype=float)
    present = weights > 0
    if int(present.sum()) > max_points:
        rng = np.random.default_rng(seed)
        return np.sort(rng.choice(valid_flat, size=max_points, replace=False))
    quotas = np.zeros(3, dtype=int)
    quotas[present] = 1
    remaining = max_points - int(quotas.sum())
    if remaining:
        shares = weights / weights.sum() * remaining
        quotas += np.floor(shares).astype(int)
        # Distribute rounding remainder by largest fractional share.
        for idx in np.argsort(-(shares - np.floor(shares)))[: max_points - int(quotas.sum())]:
            quotas[idx] += 1
    rng = np.random.default_rng(seed)
    selected = []
    for group, quota in zip(groups, quotas):
        if quota <= 0 or len(group) == 0:
            continue
        # Evenly spaced source indices preserve broad spatial coverage and avoid
        # random clustering; randomized tie-breaking makes repeated values fair.
        if quota >= len(group):
            selected.append(group)
        else:
            positions = np.linspace(0, len(group) - 1, quota, dtype=np.int64)
            selected.append(group[positions])
    chosen = np.unique(np.concatenate(selected))
    # Keep the true shadow and illumination extremes even if they fall between
    # the evenly spaced samples of a broad class.
    extremes = np.array([
        valid_flat[np.argmin(flat_values[valid_flat])],
        valid_flat[np.argmax(flat_values[valid_flat])],
    ], dtype=np.int64)
    chosen = np.unique(np.concatenate((chosen, extremes)))
    if len(chosen) > max_points:
        removable = np.setdiff1d(chosen, extremes, assume_unique=True)
        keep_count = max_points - len(extremes)
        keep = rng.choice(removable, keep_count, replace=False) if keep_count > 0 else np.array([], dtype=np.int64)
        chosen = np.sort(np.unique(np.concatenate((keep, extremes))))
    elif len(chosen) < max_points:
        remainder = np.setdiff1d(valid_flat, chosen, assume_unique=False)
        extra = min(max_points - len(chosen), len(remainder))
        if extra:
            chosen = np.sort(np.concatenate([chosen, remainder[np.linspace(0, len(remainder)-1, extra, dtype=np.int64)]]))
    return chosen


def process(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT,
            max_points: int = 20_000) -> dict[str, Any]:
    if max_points < 1:
        raise ValueError("max_points must be at least 1")
    with rasterio.open(input_path) as src:
        if src.crs is None:
            raise ValueError("Input GeoTIFF has no CRS; cannot safely convert coordinates.")
        values, value_info = _clean_values(src)
        transform = src.transform
        # Pixel centers in the native projected CRS, in the source units.
        rows, cols = np.indices(values.shape)
        xs = transform.c + (cols + 0.5) * transform.a + (rows + 0.5) * transform.b
        ys = transform.f + (cols + 0.5) * transform.d + (rows + 0.5) * transform.e

        geographic_crs = src.crs.geodetic_crs
        if geographic_crs is None:
            raise ValueError(f"CRS {src.crs} has no associated geographic CRS.")
        transformer = Transformer.from_crs(src.crs, geographic_crs, always_xy=True)
        lon_all, lat_all = transformer.transform(xs, ys)
        valid = np.isfinite(values) & np.isfinite(lat_all) & np.isfinite(lon_all)
        # The source raster is a square map tile, whose corners extend north of
        # the advertised 65S footprint. Keep only the requested 65S–90S region.
        valid &= (lat_all >= -90.0) & (lat_all <= -65.0)
        # Normalize the antimeridian to the conventional closed interval.
        lon_all = (lon_all + 180.0) % 360.0 - 180.0
        values[~valid] = np.nan

        indices = _sample_indices(values, max_points)
        row_idx, col_idx = np.unravel_index(indices, values.shape)
        sampled_lat = lat_all[row_idx, col_idx]
        sampled_lon = lon_all[row_idx, col_idx]
        sampled_val = values[row_idx, col_idx]
        sampled_x = xs[row_idx, col_idx]
        sampled_y = ys[row_idx, col_idx]

        # Three.js axes: x toward lon=0, y toward lunar north, z toward lon=90E.
        lat_rad = np.radians(sampled_lat)
        lon_rad = np.radians(sampled_lon)
        cos_lat = np.cos(lat_rad)
        vectors = np.column_stack((cos_lat * np.cos(lon_rad), np.sin(lat_rad), cos_lat * np.sin(lon_rad)))

        points = [
            {
                "lat": round(float(lat), 7),
                "lon": round(float(lon), 7),
                "proj_x_m": round(float(x), 3),
                "proj_y_m": round(float(y), 3),
                "three_pos": [round(float(component), 8) for component in vector],
                "illumination_pct": round(float(value), 6),
            }
            for lat, lon, x, y, vector, value in zip(sampled_lat, sampled_lon, sampled_x, sampled_y, vectors, sampled_val)
        ]
        crs_text = src.crs.to_string()
        crs_wkt = src.crs.to_wkt()
        proj4 = src.crs.to_proj4()
        raster_metadata = {
            "width": src.width,
            "height": src.height,
            "transform": [float(v) for v in transform],
            "resolution_native_units": [float(v) for v in src.res],
            "nodata": value_info["nodata"],
            "scales": [float(v) for v in src.scales],
            "offsets": [float(v) for v in src.offsets],
            "value_encoding": value_info["detected_value_encoding"],
            "scale_applied": value_info["scale"],
            "offset_applied": value_info["offset"],
            "source_bounds": [float(src.bounds.left), float(src.bounds.bottom), float(src.bounds.right), float(src.bounds.top)],
        }

    finite_all = values[np.isfinite(values)]
    if not points:
        raise ValueError("No valid pixels remained after applying the latitude and value masks.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "metadata": {
            "dataset": DATASET,
            "source": SOURCE,
            "source_file": input_path.name,
            "region": "Lunar South Pole (65°S to 90°S)",
            "original_crs": crs_text,
            "original_crs_wkt": crs_wkt,
            "original_crs_proj4": proj4,
            "geographic_crs": geographic_crs.to_string(),
            "lunar_radius_m": LUNAR_RADIUS_M,
            "unit": "percent_time_illuminated",
            "value_range": [0.0, 100.0],
            "point_count": len(points),
            "max_points": max_points,
            "raster": raster_metadata,
            "valid_pixel_count": int(finite_all.size),
            "sampled_value_min": float(min(p["illumination_pct"] for p in points)),
            "sampled_value_max": float(max(p["illumination_pct"] for p in points)),
            "illumination_meaning": "Long-term average percentage of time receiving direct solar illumination over the lunar nodal cycle.",
        },
        "points": points,
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        handle.write("\n")

    print("NASA lunar illumination raster")
    print(f"  Input: {input_path}")
    print(f"  CRS: {crs_text}")
    print(f"  CRS WKT: {crs_wkt}")
    print(f"  CRS Proj4: {proj4}")
    print(f"  Affine transform: {transform}")
    print(f"  Pixel resolution: {src.res} native CRS units")
    print(f"  Dimensions: {raster_metadata['width']} x {raster_metadata['height']}")
    print(f"  Nodata: {raster_metadata['nodata']}; scales: {raster_metadata['scales']}; offsets: {raster_metadata['offsets']}")
    print(f"  Valid illumination range: {finite_all.min():.6g}–{finite_all.max():.6g}%")
    print(f"  Valid pixels: {finite_all.size}; exported points: {len(points)}")
    print(f"  JSON: {output_path} ({output_path.stat().st_size:,} bytes)")
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input NASA illumination GeoTIFF")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output JSON path")
    parser.add_argument("--max-points", type=int, default=20_000, help="Maximum output points (default: 20000)")
    args = parser.parse_args()
    process(args.input, args.output, args.max_points)


if __name__ == "__main__":
    main()
