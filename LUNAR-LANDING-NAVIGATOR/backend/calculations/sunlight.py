"""Download NASA LOLA polar illumination and export sampled values as CSV."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import rasterio
import requests

# NASA GSFC PGDA: 85S-90S average solar illumination, 60 m/pixel.
NASA_TIFF_URL = "https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608.TIF"
BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data_storage"
DEFAULT_TIFF = DATA_DIR / "nasa_lunar_illumination_85s_60m.tif"
DEFAULT_CSV = DATA_DIR / "nasa_lunar_south_pole_sunlight.csv"
MOON_RADIUS_KM = 1737.4


def download_illumination(output_path: Path = DEFAULT_TIFF, timeout: int = 120) -> Path:
    """Download the official NASA illumination GeoTIFF; this product needs no API key."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(NASA_TIFF_URL, timeout=timeout, stream=True)
    response.raise_for_status()
    if "text/html" in response.headers.get("Content-Type", "").lower():
        raise RuntimeError(f"NASA returned HTML instead of a GeoTIFF: {NASA_TIFF_URL}")
    partial = output_path.with_suffix(output_path.suffix + ".part")
    try:
        with partial.open("wb") as output:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    output.write(chunk)
        if partial.stat().st_size < 1024:
            raise RuntimeError("NASA download is unexpectedly small; no raster saved.")
        partial.replace(output_path)
    finally:
        partial.unlink(missing_ok=True)
        response.close()
    return output_path


def south_polar_xy_to_latlon(x_km: float, y_km: float) -> tuple[float, float]:
    """Convert south-polar stereographic kilometres to approximate selenographic degrees."""
    rho = float(np.hypot(x_km, y_km))
    lat = -90.0 + np.degrees(2.0 * np.arctan2(rho, 2.0 * MOON_RADIUS_KM))
    lon = float(np.degrees(np.arctan2(x_km, y_km))) if rho else 0.0
    return float(lat), lon


def export_illumination_csv(tiff_path: Path = DEFAULT_TIFF, csv_path: Path = DEFAULT_CSV,
                            max_rows: int = 300, max_cols: int = 300) -> Path:
    """Downsample valid raster pixels and write their coordinates and sunlight percentages."""
    tiff_path, csv_path = Path(tiff_path), Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tiff_path) as src:
        out_h, out_w = min(max_rows, src.height), min(max_cols, src.width)
        values = src.read(1, out_shape=(out_h, out_w), masked=True,
                          resampling=rasterio.enums.Resampling.average)
        rows, cols = np.indices(values.shape)
        source_rows = (rows + 0.5) * src.height / out_h
        source_cols = (cols + 0.5) * src.width / out_w
        xs, ys = rasterio.transform.xy(src.transform, source_rows, source_cols, offset="ul")
        valid = ~np.ma.getmaskarray(values) & np.isfinite(np.ma.filled(values, np.nan))
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["latitude_deg", "longitude_deg", "illumination_percent",
                             "x_km", "y_km", "source", "source_resolution_m"])
            for row, col in zip(*np.nonzero(valid)):
                x_km, y_km = float(xs[row][col]) / 1000.0, float(ys[row][col]) / 1000.0
                lat, lon = south_polar_xy_to_latlon(x_km, y_km)
                value = float(np.clip(values[row, col], 0.0, 100.0))
                writer.writerow([f"{lat:.6f}", f"{lon:.6f}", f"{value:.4f}",
                                 f"{x_km:.4f}", f"{y_km:.4f}", "NASA LOLA / PGDA", "60"])
    return csv_path


def fetch_and_save(csv_path: Path = DEFAULT_CSV, tiff_path: Path = DEFAULT_TIFF) -> Path:
    """Download NASA's raster and save the reusable CSV under backend/data_storage/."""
    download_illumination(tiff_path)
    result = export_illumination_csv(tiff_path, csv_path)
    print(f"Saved NASA lunar sunlight samples to {result}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--tiff", type=Path, default=DEFAULT_TIFF)
    parser.add_argument("--from-local-tiff", action="store_true",
                        help="convert an already downloaded GeoTIFF without requesting NASA")
    args = parser.parse_args()
    if args.from_local_tiff:
        result = export_illumination_csv(args.tiff, args.csv)
        print(f"Saved NASA lunar sunlight samples to {result}")
    else:
        fetch_and_save(args.csv, args.tiff)


if __name__ == "__main__":
    main()
