"""Terrain slope calculations for lunar elevation grids."""

from __future__ import annotations

import numpy as np

LUNAR_RADIUS_M = 1_737_400.0


def geographic_pixel_size_m(
    pixel_width_degrees: float,
    pixel_height_degrees: float,
    latitude_degrees: float,
    *,
    lunar_radius_m: float = LUNAR_RADIUS_M,
) -> tuple[float, float]:
    """Convert angular pixel dimensions to local metres on the Moon.

    Returns (east_west_pixel_size_m, north_south_pixel_size_m).
    """
    lat_rad = np.deg2rad(latitude_degrees)
    x_m = np.deg2rad(abs(pixel_width_degrees)) * lunar_radius_m * abs(np.cos(lat_rad))
    y_m = np.deg2rad(abs(pixel_height_degrees)) * lunar_radius_m
    if x_m == 0 or y_m == 0:
        raise ValueError("pixel dimensions must be non-zero")
    return float(x_m), float(y_m)


def calculate_slope(
    elevation_m: np.ndarray,
    pixel_size_x_m: float,
    pixel_size_y_m: float,
) -> np.ndarray:
    """Calculate terrain slope in degrees from a DEM in metres.

    ``pixel_size_x_m`` and ``pixel_size_y_m`` are ground distances between
    adjacent pixel centers. For a geographic grid use
    :func:`geographic_pixel_size_m`; for a projected lunar grid use its linear
    pixel resolution directly. Missing elevation cells remain NaN.
    """
    dem = np.asarray(elevation_m, dtype=float)
    if dem.ndim != 2 or min(dem.shape) < 2:
        raise ValueError("elevation_m must be a 2D grid at least 2x2")
    if pixel_size_x_m <= 0 or pixel_size_y_m <= 0:
        raise ValueError("pixel sizes must be positive metres")

    valid = np.isfinite(dem)
    if not valid.all():
        # Fill only for gradient evaluation, then mask output around missing data.
        fill_value = float(np.nanmedian(dem)) if valid.any() else 0.0
        work = np.where(valid, dem, fill_value)
    else:
        work = dem
    gradient_y, gradient_x = np.gradient(work, pixel_size_y_m, pixel_size_x_m)
    slope = np.degrees(np.arctan(np.hypot(gradient_x, gradient_y)))
    slope[~valid] = np.nan
    return slope


def calculate_slope_from_geographic_grid(
    elevation_m: np.ndarray,
    pixel_width_degrees: float,
    pixel_height_degrees: float,
    latitude_degrees: float = -87.5,
) -> np.ndarray:
    """Convenience wrapper for a regular latitude/longitude DEM grid."""
    pixel_x_m, pixel_y_m = geographic_pixel_size_m(
        pixel_width_degrees, pixel_height_degrees, latitude_degrees
    )
    return calculate_slope(elevation_m, pixel_x_m, pixel_y_m)
