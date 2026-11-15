"""Solar energy yield from average lunar illumination."""

from __future__ import annotations

import numpy as np

LUNAR_SOLAR_CONSTANT_W_M2 = 1361.0
DEFAULT_PANEL_EFFICIENCY = 0.20
HOURS_PER_LUNAR_DAY = 24.0


def calculate_solar_potential(
    illumination_percent: np.ndarray,
    *,
    panel_efficiency: float = DEFAULT_PANEL_EFFICIENCY,
    solar_constant_w_m2: float = LUNAR_SOLAR_CONSTANT_W_M2,
) -> np.ndarray:
    """Estimate average energy yield in kWh/m²/day from illumination (0-100%).

    This uses the supplied average illuminated fraction as a daily-equivalent
    sunlight fraction: solar constant × 24 h × panel efficiency. It is a planning
    estimate, not instantaneous power or a mission-specific thermal model.
    """
    illumination = np.asarray(illumination_percent, dtype=float)
    if not 0.0 <= panel_efficiency <= 1.0:
        raise ValueError("panel_efficiency must be between 0 and 1")
    if solar_constant_w_m2 <= 0:
        raise ValueError("solar_constant_w_m2 must be positive")
    clipped = np.clip(illumination, 0.0, 100.0)
    energy = (
        solar_constant_w_m2
        * (clipped / 100.0)
        * HOURS_PER_LUNAR_DAY
        * panel_efficiency
        / 1000.0
    )
    return np.where(np.isfinite(illumination), energy, np.nan)
