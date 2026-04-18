"""
test_subroutines.py — Unit tests for WAIT, COST, and PERFM.

Reference values were captured from verified Python runs and, where available,
compared against the NASA CR-2066 Fortran reference values.  Tolerances are
set to 0.5 % for smooth physics quantities and 1 % for tabulated lookups.
"""
import numpy as np
import pytest
from common import CommonAFCOR, CommonCPECTE, CommonASTRK
from constants import (T0_RANKINE, T0_ISA, LAPSE_RATE,
                       SPEED_OF_SOUND, MACH_KTAS_FACTOR, J_CONV,
                       RPM_FACTOR, THRUST_DENOM, THRUST_CONV)
from UNINT import unint
from WAIT  import wait
from COST  import cost
from PERFM import perfm

import numpy as np
_ALTPR  = np.array([0., 10000., 20000., 30000., 40000., 50000.,
                    60000., 70000., 80000., 90000., 100000.])
_PRESSR = np.array([1.0, 0.6877, 0.4595, 0.2970, 0.1851, 0.1145,
                    0.07078, 0.04419, 0.02741, 0.01699, 0.01054])


# ======================================================================
# WAIT — propeller weight estimation
# ======================================================================

class TestWAIT:

    def test_wtcon_zero_returns_zeros(self):
        """WTCON ≤ 0 is the 'skip' sentinel; both weights must be 0."""
        wt70, wt80 = wait(0.0, 0.327, 340.0, 8.0, 200.0, 4.0, 700.0)
        assert wt70 == 0.0
        assert wt80 == 0.0

    def test_negative_wtcon_returns_zeros(self):
        wt70, wt80 = wait(-1.0, 0.327, 340.0, 8.0, 200.0, 4.0, 700.0)
        assert wt70 == 0.0
        assert wt80 == 0.0

    def test_4_blade_stall_case(self):
        """
        4-blade propeller from the stall/cost integration test.
        Inputs:  WTCON=4, ZMWT=0.327, BHP=340, D=8ft, AF=200, BLADN=4, Vt=344.4 fps
        Expected: WT70 ≈ 228.0 lb, WT80 ≈ 185.2 lb
        """
        wt70, wt80 = wait(4.0, 0.327, 340.0, 8.0, 200.0, 4.0, 344.4)
        assert wt70 == pytest.approx(228.0, rel=0.005)
        assert wt80 == pytest.approx(185.2, rel=0.005)

    def test_6_blade_stall_case(self):
        """
        6-blade propeller from the stall/cost integration test.
        Inputs:  WTCON=4, ZMWT=0.327, BHP=340, D=8ft, AF=200, BLADN=6, Vt=281.9 fps
        Expected: WT70 ≈ 305.8 lb, WT80 ≈ 245.4 lb
        """
        wt70, wt80 = wait(4.0, 0.327, 340.0, 8.0, 200.0, 6.0, 281.9)
        assert wt70 == pytest.approx(305.8, rel=0.005)
        assert wt80 == pytest.approx(245.4, rel=0.005)

    def test_heavier_blades_weigh_more(self):
        """More blades must produce a heavier propeller (monotone in BLADN)."""
        wt70_4, _ = wait(2.0, 0.262, 300.0, 7.0, 150.0, 4.0, 800.0)
        wt70_6, _ = wait(2.0, 0.262, 300.0, 7.0, 150.0, 6.0, 800.0)
        assert wt70_6 > wt70_4


# ======================================================================
# COST — propeller weight/cost estimation
# ======================================================================

class TestCOST:

    def _init_cost(self, wtcon=4.0, bladt=4.0):
        """Run IENT=1 (initialise cost factors) and return (CCLF1, CCLF)."""
        cquan = np.zeros((2, 11))
        cost70 = np.zeros(10)
        cost80 = np.zeros(10)
        CCLF1, CCLF, *_ = cost(
            wtcon, bladt, 0.0, 0.0, 0.0, 0.0,
            1.0, 1000.0, 5, cquan,
            0.0, 0.0, cost70, cost80,
            0.0, 0.0, 0.0, 0.0, 1)
        return CCLF1, CCLF

    def test_init_returns_nonzero_factors(self):
        """IENT=1 must set CLF factors to non-zero values (default learning curve)."""
        CCLF1, CCLF = self._init_cost()
        assert CCLF1 > 0.0
        assert CCLF  > 0.0

    def test_cost_4blade_at_qty1(self):
        """
        4-blade stall-case cost at qty=1 unit.
        Expected: Cost70 ≈ $7105, Cost80 ≈ $7770 (from test_stall_cost run).
        """
        cquan   = np.zeros((2, 11))
        cost70  = np.zeros(10)
        cost80  = np.zeros(10)
        CCLF1, CCLF = self._init_cost(wtcon=4.0, bladt=4.0)
        wt70, wt80 = wait(4.0, 0.327, 340.0, 8.0, 200.0, 4.0, 344.4)
        _, _, _, _, cquan_out, c70_out, c80_out = cost(
            4.0, 4.0, 0.0, 0.0, 0.0, 0.0,
            1.0, 1000.0, 5, cquan,
            wt70, wt80, cost70, cost80,
            CCLF1, CCLF, 0.0, 0.0, 2)
        assert c70_out[0] == pytest.approx(7105, rel=0.01)
        assert c80_out[0] == pytest.approx(7770, rel=0.01)

    def test_higher_qty_lower_unit_cost(self):
        """Unit cost at qty=4001 must be lower than at qty=1 (learning curve)."""
        cquan  = np.zeros((2, 11))
        cost70 = np.zeros(10)
        cost80 = np.zeros(10)
        CCLF1, CCLF = self._init_cost(wtcon=4.0, bladt=4.0)
        wt70, wt80 = wait(4.0, 0.327, 340.0, 8.0, 200.0, 4.0, 344.4)
        _, _, _, _, _, c70_out, _ = cost(
            4.0, 4.0, 0.0, 0.0, 0.0, 0.0,
            1.0, 1000.0, 5, cquan,
            wt70, wt80, cost70, cost80,
            CCLF1, CCLF, 0.0, 0.0, 2)
        # qty=1 cost is at index 0; qty=4001 cost is at index 4
        assert c70_out[4] < c70_out[0]


# ======================================================================
# PERFM — propeller aerodynamic performance lookup
# ======================================================================

def _make_common():
    return CommonAFCOR(), CommonCPECTE(), CommonASTRK()


def _atmosphere(alt_ft, T_user_f=0.0, dt_isa=0.0):
    """Compute (RORO, FC) for a given altitude and optional temperature."""
    if T_user_f <= 0.0:
        T_R = (T0_ISA - LAPSE_RATE * alt_ft + dt_isa
               if alt_ft <= 36000.0 else 389.988 + dt_isa)
    else:
        T_R = T_user_f + 459.69
    TOT = T0_RANKINE / T_R
    FC  = float(np.sqrt(TOT))
    POP, _ = unint(11, _ALTPR, _PRESSR, alt_ft)
    RORO = 1.0 / (POP * TOT)
    return RORO, FC


class TestPERFM:

    # ── IW=1 (fixed BHP) ────────────────────────────────────────────

    def test_iw1_off_chart_sentinel(self):
        """
        At an extreme advance ratio (J=4.5) for a low-AF propeller,
        PERFM should return the ASTERK off-chart sentinel on CPE or CTE.
        """
        afc, cpe, ast = _make_common()
        ZMS = np.array([0.5, 0.8])
        perfm(1, 0.05, 4.5, 80.0, 2.0, 0.5, 0.0, ZMS, 0, afc, cpe, ast)
        off = (cpe.CPE >= ast.ASTERK or cpe.CTE >= ast.ASTERK)
        assert off, "Expected off-chart for J=4.5 at low AF"

    def test_iw1_condition2_point0(self):
        """
        IW=1 — Condition 2 (ALT=7500 ft, T=32.33°F),
        D=6 ft, Vt=850 fps.  AF=150, BLADN=4, CLi=0.5.
        CP and CT regression values from verified Python run.
        Note: IW=1 iterates from CP→CT, so CTE differs slightly from the
        IW=2 (CT-driven) value of 0.073949 captured in the integration test.
        """
        RORO, FC = _atmosphere(7500.0, T_user_f=32.33)
        TIPSPD = 850.0; DIA = 6.0; BHP_ref = 226.3
        CP_in = BHP_ref * 1e11 * RORO / (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR)
        VKTAS = 163.2
        J     = J_CONV * VKTAS / TIPSPD
        ZMS   = np.zeros(2)
        ZMS[0] = MACH_KTAS_FACTOR * VKTAS * FC
        ZMS[1] = TIPSPD * FC / SPEED_OF_SOUND
        afc, cpe, ast = _make_common()
        perfm(1, CP_in, J, 150.0, 4.0, 0.5, 0.0, ZMS, 0, afc, cpe, ast)
        assert cpe.CPE < ast.ASTERK, "Result must not be off-chart"
        assert cpe.CPE == pytest.approx(0.091947, rel=0.005)
        assert cpe.CTE == pytest.approx(0.07952,  rel=0.01)
        assert cpe.BLLLL == pytest.approx(23.48,   abs=0.5)

    def test_iw1_condition2_point1(self):
        """
        IW=1 — D=6 ft, Vt=750 fps (second tip-speed point).
        SHP=212.9 from integration test; CPE must match the integration CP value.
        D=8/Vt=850 is excluded: that (AF=150, low-CP) point falls off-chart in
        IW=1 mode because the CP is below the table's minimum blade loading.
        """
        RORO, FC = _atmosphere(7500.0, T_user_f=32.33)
        TIPSPD = 750.0; DIA = 6.0; BHP_ref = 212.9
        CP_in = BHP_ref * 1e11 * RORO / (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR)
        VKTAS = 163.2
        J     = J_CONV * VKTAS / TIPSPD
        ZMS   = np.zeros(2)
        ZMS[0] = MACH_KTAS_FACTOR * VKTAS * FC
        ZMS[1] = TIPSPD * FC / SPEED_OF_SOUND
        afc, cpe, ast = _make_common()
        perfm(1, CP_in, J, 150.0, 4.0, 0.5, 0.0, ZMS, 0, afc, cpe, ast)
        assert cpe.CPE < ast.ASTERK, "Result must not be off-chart"
        assert cpe.CPE == pytest.approx(0.125907, rel=0.005)

    # ── IW=2 (fixed thrust) ─────────────────────────────────────────

    def test_iw2_condition2_point0(self):
        """
        IW=2 — same geometry as IW=1 test but driven by thrust input.
        CT is computed from THRUST=370 lbf; PERFM must return consistent CP.
        """
        RORO, FC = _atmosphere(7500.0, T_user_f=32.33)
        TIPSPD = 850.0; DIA = 6.0; THRUST = 370.0
        CT_in = THRUST * THRUST_DENOM * RORO / (TIPSPD**2 * DIA**2 * THRUST_CONV)
        VKTAS = 163.2
        J     = J_CONV * VKTAS / TIPSPD
        ZMS   = np.zeros(2)
        ZMS[0] = MACH_KTAS_FACTOR * VKTAS * FC
        ZMS[1] = TIPSPD * FC / SPEED_OF_SOUND
        afc, cpe, ast = _make_common()
        perfm(2, 0.0, J, 150.0, 4.0, 0.5, CT_in, ZMS, 0, afc, cpe, ast)
        assert cpe.CPE < ast.ASTERK
        assert cpe.CTE == pytest.approx(0.073949, rel=0.01)

    # ── Monotonicity sanity checks ───────────────────────────────────

    def test_efficiency_increases_with_J_at_low_J(self):
        """
        η = J·CT/CP should increase with J from J=0 up to the design J.
        Tested over J = 0.2, 0.5, 0.8 for a typical propeller.
        """
        RORO, FC = _atmosphere(0.0)
        TIPSPD = 800.0; DIA = 7.0; BHP = 300.0
        CP_in = BHP * 1e11 * RORO / (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR)
        etas = []
        for J in [0.2, 0.5, 0.8]:
            VKTAS = J * TIPSPD / J_CONV
            ZMS   = np.zeros(2)
            ZMS[0] = MACH_KTAS_FACTOR * VKTAS * FC
            ZMS[1] = TIPSPD * FC / SPEED_OF_SOUND
            afc, cpe, ast = _make_common()
            perfm(1, CP_in, J, 120.0, 3.0, 0.5, 0.0, ZMS, 0, afc, cpe, ast)
            if cpe.CPE < ast.ASTERK and cpe.CTE < ast.ASTERK and cpe.CPE > 0:
                etas.append(J * cpe.CTE / cpe.CPE)
        assert len(etas) >= 2
        assert etas[-1] > etas[0], "Efficiency must rise from low J"

    def test_ct_decreases_with_J(self):
        """
        At fixed blade angle (fixed power, varying airspeed), thrust coefficient
        must decrease monotonically as J increases.
        """
        RORO, FC = _atmosphere(0.0)
        TIPSPD = 800.0; DIA = 7.0; BHP = 300.0
        CP_in = BHP * 1e11 * RORO / (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR)
        cts = []
        for J in [0.4, 0.8, 1.2]:
            VKTAS = J * TIPSPD / J_CONV
            ZMS   = np.zeros(2)
            ZMS[0] = MACH_KTAS_FACTOR * VKTAS * FC
            ZMS[1] = TIPSPD * FC / SPEED_OF_SOUND
            afc, cpe, ast = _make_common()
            perfm(1, CP_in, J, 120.0, 3.0, 0.5, 0.0, ZMS, 0, afc, cpe, ast)
            if cpe.CTE < ast.ASTERK:
                cts.append(cpe.CTE)
        assert len(cts) >= 2
        assert cts[-1] < cts[0], "CT must decrease with rising J"
