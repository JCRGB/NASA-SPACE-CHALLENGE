"""Reusable calculations for lunar landing-site raster grids."""

from __future__ import annotations

import numpy as np

from .solar_energy import calculate_solar_potential
from .suitability import calculate_suitability
from .terrain import calculate_slope


def calculate_site_metrics(
    elevation_m: np.ndarray,
    illumination_percent: np.ndarray,
    pixel_size_x_m: float,
    pixel_size_y_m: float,
    *,
    slope_weight: float = 0.5,
    solar_weight: float = 0.3,
    ice_weight: float = 0.2,
) -> dict[str, np.ndarray]:
    """Calculate slope, solar yield, and landing suitability for aligned grids."""
    elevation = np.asarray(elevation_m, dtype=float)
    illumination = np.asarray(illumination_percent, dtype=float)
    if elevation.shape != illumination.shape:
        raise ValueError("elevation and illumination arrays must have identical shapes")

    slope_degrees = calculate_slope(elevation, pixel_size_x_m, pixel_size_y_m)
    solar_kwh_m2_day = calculate_solar_potential(illumination)
    suitability_score, risk_rating = calculate_suitability(
        slope_degrees,
        illumination,
        slope_weight=slope_weight,
        solar_weight=solar_weight,
        ice_weight=ice_weight,
        pixel_size_m=float(np.sqrt(pixel_size_x_m * pixel_size_y_m)),
    )
    return {
        "elevation_m": elevation,
        "illumination_percent": illumination,
        "slope_degrees": slope_degrees,
        "solar_kwh_m2_day": solar_kwh_m2_day,
        "suitability_score": suitability_score,
        "risk_rating": risk_rating,
    }


__all__ = [
    "calculate_site_metrics",
    "calculate_slope",
    "calculate_solar_potential",
    "calculate_suitability",
]
