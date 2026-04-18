"""
operating_condition.py — Typed input contract for the NASA CR-2066 propeller program.

Replaces the Fortran perf-card (punch-card) INPUT subroutine with a clean Python
dataclass.  The HMI simply fills a list of OperatingCondition objects and passes
it to load_conditions(); the rest of the program never needs to parse raw cards.

IW codes
--------
    1  — shaft horsepower (BHP) specified
    2  — thrust (lbf) specified
    3  — reverse-thrust calculation

Validation
----------
Each field has an acceptable range documented in its comment.  Call
validate() on an OperatingCondition to raise ValueError before passing it
to the solver, catching data-entry mistakes as early as possible.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class OperatingCondition:
    """
    One operating condition (one row of the original perf card deck).

    All fields map 1-to-1 to the corresponding COMMON /ZINPUT/ array element
    so that load_conditions() can fill PropellerState without any guesswork.
    """

    # ── Required ─────────────────────────────────────────────────────────
    IW:     int    # computation mode: 1=HP, 2=thrust, 3=reverse thrust

    # ── Power / thrust input (one of these must be non-zero) ─────────────
    BHP:    float = 0.0    # shaft horsepower (used when IW=1 or IW=3)
    THRUST: float = 0.0    # thrust target in lbf (used when IW=2)

    # ── Flight condition ─────────────────────────────────────────────────
    ALT:   float = 0.0    # altitude, feet (0 – 100 000)
    VKTAS: float = 0.0    # true airspeed, knots (≥ 0)
    T:      float = 0.0    # temperature, °F  (≤0 → compute from standard atmosphere)
    DT_ISA: float = 0.0    # ISA temperature deviation, °F (+ hot day, – cold day)
                            # applied only when T ≤ 0 (ISA day)

    # ── Tip-speed sweep ──────────────────────────────────────────────────
    TS:    float = 0.0    # starting tip speed, ft/s
    DTS:   float = 0.0    # tip-speed increment, ft/s
    NDTS:  int   = 1      # number of tip-speed steps (1 – 10)

    # ── Noise ────────────────────────────────────────────────────────────
    DIST:  float = 0.0    # sideline distance for noise, ft (≤0 → skip noise)

    # ── Stall option ─────────────────────────────────────────────────────
    STALIT: float = 0.0   # > 0.5 → iterate to 50 % stall tip speed

    # ── Cost ─────────────────────────────────────────────────────────────
    DCOST: float = 0.0    # cost flag: 1 = compute weight/cost, 0 = skip
                          # (aircraft category is set by WTCON in PropellerGeometry)

    # ── Reverse-thrust specific (IW = 3) ─────────────────────────────────
    RPMC:  float = 0.0    # full-throttle RPM for reverse thrust
    ANDVK: float = 0.0    # touch-down speed, knots
    PCPW:  float = 100.0  # power setting, % (default full power)
    NPCPW: int   = 1      # number of power settings
    DPCPW: float = 0.0    # power-setting increment, %
    BETA:  float = 0.0    # blade angle (used when RTC ≠ 1)

    # ── Validation ranges ────────────────────────────────────────────────
    _IW_VALID    = (1, 2, 3)
    _ALT_RANGE   = (0.0, 100_000.0)
    _VKTAS_MIN   = 0.0
    _NDTS_RANGE  = (1, 10)

    def validate(self) -> None:
        """
        Raise ValueError if any field is out of its acceptable range.
        Call this before passing the condition to load_conditions().
        """
        if self.IW not in self._IW_VALID:
            raise ValueError(f"IW={self.IW} invalid; must be 1, 2, or 3")
        if self.IW == 1 and self.BHP <= 0.0:
            raise ValueError(f"IW=1 requires BHP > 0 (got {self.BHP})")
        if self.IW == 2 and self.THRUST <= 0.0:
            raise ValueError(f"IW=2 requires THRUST > 0 (got {self.THRUST})")
        lo, hi = self._ALT_RANGE
        if not (lo <= self.ALT <= hi):
            raise ValueError(f"ALT={self.ALT} out of range [{lo}, {hi}]")
        if self.VKTAS < self._VKTAS_MIN:
            raise ValueError(f"VKTAS={self.VKTAS} must be ≥ 0")
        lo, hi = self._NDTS_RANGE
        if not (lo <= self.NDTS <= hi):
            raise ValueError(f"NDTS={self.NDTS} out of range [{lo}, {hi}]")
        if self.IW == 3:
            if self.RPMC <= 0.0:
                raise ValueError(f"IW=3 requires RPMC > 0 (got {self.RPMC})")
            if self.ANDVK <= 0.0:
                raise ValueError(f"IW=3 requires ANDVK > 0 (got {self.ANDVK})")


@dataclass
class PropellerGeometry:
    """
    Propeller design-space sweep parameters (same for all operating conditions).
    Maps to the scalar geometry fields of COMMON /ZINPUT/.
    """
    # ── Diameter sweep ────────────────────────────────────────────────────
    D:    float  # starting diameter, ft   (80 ≤ AF ≤ 200)
    DD:   float  # diameter increment, ft
    ND:   int    # number of diameters

    # ── Activity-factor sweep ─────────────────────────────────────────────
    AF:   float  # starting blade activity factor BAF, per blade  (80 – 200)
                 # TAF (total propeller) = BAF × number of blades
    DAF:  float  # AF increment
    NAF:  int    # number of AF values

    # ── Blade number sweep ────────────────────────────────────────────────
    BLADN: float # starting blade count       (2 – 8)
    DBLAD: float # blade-count increment
    NBL:   int   # number of blade counts

    # ── Design-CLi sweep ──────────────────────────────────────────────────
    CLII:  float # starting integrated design CL   (0.3 – 0.8)
    DCLI:  float # CLi increment
    ZNCLI: int   # number of CLi values

    # ── Design Mach number ────────────────────────────────────────────────
    ZMWT:  float # design flight Mach number (used for weight/cost)

    # ── Classification / cost ─────────────────────────────────────────────
    WTCON: float = 0.0   # airplane category weight constant (1–5)
    XNOE:  float = 1.0   # number of engines
    CLF1:  float = 0.0   # learning-curve factor 1 (0 → use default 3.2178)
    CLF:   float = 0.0   # learning-curve factor 2 (0 → use default 1.02)
    CK70:  float = 0.0   # 1970 cost slope (0 → compute from category)
    CK80:  float = 0.0   # 1980 cost slope (0 → compute from category)
    CAMT:  float = 0.0   # starting production quantity (0 → use default)
    DAMT:  float = 500.0 # quantity increment
    NAMT:  int   = 1     # number of quantity breakpoints

    # ── Reverse-thrust engine type ────────────────────────────────────────
    RTC:   float = 0.0   # reverse-thrust control flag: 1.0 = compute β from CP, 2.0 = β given
    ROT:   float = 0.0   # engine type: 1.0 = reciprocating, 2.0 = turbine

    def validate(self) -> None:
        """Raise ValueError for out-of-range geometry parameters."""
        if not (80.0 <= self.AF <= 200.0):
            raise ValueError(f"BAF (per blade)={self.AF} out of range [80, 200]")
        if not (2.0 <= self.BLADN <= 8.0):
            raise ValueError(f"BLADN={self.BLADN} out of range [2, 8]")
        if not (0.3 <= self.CLII <= 0.8):
            raise ValueError(f"CLII={self.CLII} out of range [0.3, 0.8]")
        if self.D <= 0.0:
            raise ValueError(f"D={self.D} must be > 0")
        if self.ND < 1:
            raise ValueError(f"ND={self.ND} must be ≥ 1")


def load_conditions(conditions: List[OperatingCondition],
                    geometry: PropellerGeometry,
                    state) -> None:
    """
    Fill a PropellerState from a validated list of OperatingConditions
    and a PropellerGeometry.  This replaces CALL INPUT in the Fortran.

    Parameters
    ----------
    conditions : list of OperatingCondition, len ≤ 10
    geometry   : PropellerGeometry (design-space sweep parameters)
    state      : PropellerState instance (from MAIN.py)
    """
    if len(conditions) == 0:
        raise ValueError("At least one OperatingCondition is required")
    if len(conditions) > 10:
        raise ValueError(f"Maximum 10 operating conditions; got {len(conditions)}")

    # Validate all before touching state (fail-fast)
    geometry.validate()
    for i, cond in enumerate(conditions):
        try:
            cond.validate()
        except ValueError as e:
            raise ValueError(f"Operating condition {i+1}: {e}") from e

    # ── Geometry scalars ─────────────────────────────────────────────────
    state.NOF   = len(conditions)
    state.D     = geometry.D;      state.DD    = geometry.DD;    state.ND   = geometry.ND
    state.AF    = geometry.AF;     state.DAF   = geometry.DAF;   state.NAF  = geometry.NAF
    state.BLADN = geometry.BLADN;  state.DBLAD = geometry.DBLAD; state.NBL  = geometry.NBL
    state.CLII  = geometry.CLII;   state.DCLI  = geometry.DCLI;  state.ZNCLI= geometry.ZNCLI
    state.ZMWT  = geometry.ZMWT
    state.WTCON = geometry.WTCON;  state.XNOE  = geometry.XNOE
    state.CLF1  = geometry.CLF1;   state.CLF   = geometry.CLF
    state.CK70  = geometry.CK70;   state.CK80  = geometry.CK80
    state.CAMT  = geometry.CAMT;   state.DAMT  = geometry.DAMT; state.NAMT = geometry.NAMT
    state.RTC   = geometry.RTC;    state.ROT   = geometry.ROT

    # ── Per-condition arrays ──────────────────────────────────────────────
    for IC, cond in enumerate(conditions):
        state.IWIC[IC]  = cond.IW
        state.BHP[IC]   = cond.BHP
        state.THRUST[IC]= cond.THRUST
        state.ALT[IC]   = cond.ALT
        state.VKTAS[IC] = cond.VKTAS
        state.T[IC]     = cond.T
        state.DT_ISA[IC]= cond.DT_ISA
        state.TS[IC]    = cond.TS
        state.DTS[IC]   = cond.DTS
        state.NDTS[IC]  = cond.NDTS
        state.DIST[IC]  = cond.DIST
        state.STALIT[IC]= cond.STALIT
        state.DCOST[IC] = cond.DCOST
        state.RPMC[IC]  = cond.RPMC
        state.ANDVK[IC] = cond.ANDVK
        state.PCPW[IC]  = cond.PCPW
        state.NPCPW[IC] = cond.NPCPW
        state.DPCPW[IC] = cond.DPCPW
        state.BETA[IC]  = cond.BETA
