"""
units.py — Unit system definitions and conversion helpers.

The H432 computation always runs in US customary (ft-slug-s) units.
This module provides conversion factors and helpers for converting values
at the HMI and file-output boundaries.

Usage
-----
    from units import UnitSystem, FT_TO_M, HP_TO_KW, to_si, from_si, unit_label

    # Convert a result value for display
    dia_m = to_si(dia_ft, FT_TO_M, active_unit_system)

    # Convert a user input back to US before computation
    bhp   = from_si(bhp_kw, HP_TO_KW, active_unit_system)

    # Choose a unit label string
    lbl   = unit_label("ft", "m", active_unit_system)
"""

from enum import Enum


class UnitSystem(Enum):
    US = "US"
    SI = "SI"


# ── Multiply a US value by this factor to get the SI equivalent ───────────────
FT_TO_M   = 0.3048          # ft       → m
FPS_TO_MS = 0.3048          # ft/s     → m/s
HP_TO_KW  = 0.74569987      # hp (mech)→ kW
LBF_TO_N  = 4.4482216       # lbf      → N
LB_TO_KG  = 0.45359237      # lb (mass)→ kg
FTLBF_TO_NM = 1.35581795   # ft·lbf   → N·m

# Temperature offsets  (T in °F used in HMI; 0 always means "use ISA")
# T_C = (T_F - 32) * 5/9    when T_F != 0
# T_F = T_C * 9/5 + 32      when T_C != 0


def to_si(value: float, factor: float, us: UnitSystem) -> float:
    """Return *value* converted to SI when *us* is SI, else unchanged."""
    return value * factor if us == UnitSystem.SI else value


def from_si(value: float, factor: float, us: UnitSystem) -> float:
    """Convert a display value (possibly SI) back to US customary."""
    return value / factor if us == UnitSystem.SI else value


def unit_label(us_str: str, si_str: str, us: UnitSystem) -> str:
    """Return the correct unit label for the active unit system."""
    return si_str if us == UnitSystem.SI else us_str


def temp_to_display(t_f: float, us: UnitSystem) -> float:
    """Convert internal temperature (°F, 0=ISA) to display value.

    In US mode: unchanged (°F, 0=ISA).
    In SI mode: °C, 0=ISA.
    """
    if us == UnitSystem.US or t_f == 0.0:
        return t_f
    return (t_f - 32.0) * 5.0 / 9.0


def temp_from_display(t_display: float, us: UnitSystem) -> float:
    """Convert display temperature back to °F (internal, 0=ISA)."""
    if us == UnitSystem.US or t_display == 0.0:
        return t_display
    return t_display * 9.0 / 5.0 + 32.0
