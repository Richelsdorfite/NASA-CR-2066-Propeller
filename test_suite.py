"""
test_suite.py — Unit tests for the NASA CR-2066 propeller program.

Run with:  python -m pytest test_suite.py -v
       or: python test_suite.py

Covers
------
  BIQUAD  – univariate and bivariate interpolation correctness
  UNINT   – interpolation correctness, edge cases, guard clauses
  PERFM   – table layout correctness (reshape sanity)
  ZNOISE  – table layout and blade-family selection logic
  WAIT    – all 5 category formulas
  COST    – IENT dispatch, table values, cost loop
  constants – all named constants against original Fortran literals
  operating_condition – validation logic
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import numpy as np
import pytest

from BIQUAD  import biquad
from UNINT   import unint
from WAIT    import wait
from COST    import cost
from constants import (
    RHO_SCALE, RPM_FACTOR, THRUST_CONV, THRUST_DENOM,
    SPEED_OF_SOUND, T0_ISA, T_TROPO, LAPSE_RATE, T0_RANKINE,
    RPM_FROM_TIPSPD, J_CONV, MACH_KTAS_FACTOR, VK_CONV,
    THRUST_DENOM_REV,
)
from operating_condition import (
    OperatingCondition, PropellerGeometry, load_conditions,
)


# ======================================================================
# Helpers
# ======================================================================

def make_uni_table(xs, fs, table_no=1):
    """Build a univariate BIQUAD packed table (0-based)."""
    T = [float(table_no), float(len(xs)), 0.0] + list(xs) + list(fs)
    return T, 0


def make_bi_table(xs, ys, grid, table_no=1):
    """Build a bivariate BIQUAD packed table. grid[i][j] = f(xs[i], ys[j])."""
    NX, NY = len(xs), len(ys)
    data = [grid[i][j] for i in range(NX) for j in range(NY)]
    T = [float(table_no), float(NX), float(NY)] + list(xs) + list(ys) + data
    return T, 0


TOL_NUM = 1e-8   # numerical tolerance for interpolation tests
TOL_REL = 1e-6   # relative tolerance for formula tests


# ======================================================================
# BIQUAD tests
# ======================================================================

class TestBiquadUnivariate:
    def test_partition_of_unity(self):
        """f(x) = 1 everywhere → Z must be exactly 1."""
        xs = [0., 1., 2., 3., 4.]
        T, I = make_uni_table(xs, [1.0]*5)
        for x in [0.5, 1.5, 2.5, 3.5]:
            z, k = biquad(T, I, x, 0.0)
            assert abs(z - 1.0) < TOL_NUM, f"x={x}: z={z}"

    def test_linear_exact(self):
        """f(x) = 2x+1 → quadratic interpolation reproduces linear exactly."""
        xs = [0., 1., 2., 3., 4.]
        fs = [2*x+1 for x in xs]
        T, I = make_uni_table(xs, fs)
        for x in [0.3, 1.0, 1.7, 2.5, 3.8]:
            z, k = biquad(T, I, x, 0.0)
            assert abs(z - (2*x+1)) < TOL_NUM, f"x={x}"

    def test_quadratic_exact(self):
        """f(x) = x² → slope-continuous quadratic reproduces it exactly."""
        xs = [0., 1., 2., 3., 4.]
        T, I = make_uni_table(xs, [x**2 for x in xs])
        for x, exp in [(0.5, 0.25), (1.5, 2.25), (2.5, 6.25), (3.5, 12.25)]:
            z, _ = biquad(T, I, x, 0.0)
            assert abs(z - exp) < 1e-6, f"x={x}"

    def test_exact_knot_match(self):
        """Query at a knot must return the exact table value."""
        xs = [0., 1., 2., 3., 4.]
        fs = [x**2 for x in xs]
        T, I = make_uni_table(xs, fs)
        for xi in xs:
            z, _ = biquad(T, I, xi, 0.0)
            assert abs(z - xi**2) < TOL_NUM

    def test_below_range_flag(self):
        """X below table range → K=1, Z clamped to first value."""
        xs = [1., 2., 3., 4., 5.]
        T, I = make_uni_table(xs, [x**2 for x in xs])
        z, k = biquad(T, I, 0.0, 0.0)
        assert k == 1
        assert abs(z - 1.0) < TOL_NUM

    def test_above_range_flag(self):
        """X above table range → K=2, Z extrapolated from last 4 points."""
        xs = [0., 1., 2., 3., 4.]
        T, I = make_uni_table(xs, [x**2 for x in xs])
        z, k = biquad(T, I, 10.0, 0.0)
        assert k == 2


class TestBiquadBivariate:
    def test_f_xy_equals_1(self):
        """f(x,y) = 1 → Z = 1 everywhere."""
        xs = [0., 1., 2., 3., 4.]
        ys = [0., 1., 2., 3., 4.]
        grid = [[1.0]*5 for _ in range(5)]
        T, I = make_bi_table(xs, ys, grid)
        z, _ = biquad(T, I, 2.3, 1.7)
        assert abs(z - 1.0) < TOL_NUM

    def test_f_xy_equals_x(self):
        """f(x,y) = x → Z = XI."""
        xs = [0., 1., 2., 3., 4.]
        ys = [0., 1., 2., 3., 4.]
        grid = [[float(xi)]*5 for xi in xs]
        T, I = make_bi_table(xs, ys, grid)
        z, _ = biquad(T, I, 2.3, 1.7)
        assert abs(z - 2.3) < 1e-6

    def test_f_xy_equals_y(self):
        """f(x,y) = y → Z = YI."""
        xs = [0., 1., 2., 3., 4.]
        ys = [0., 1., 2., 3., 4.]
        grid = [[float(yj) for yj in ys] for _ in xs]
        T, I = make_bi_table(xs, ys, grid)
        z, _ = biquad(T, I, 2.3, 1.7)
        assert abs(z - 1.7) < 1e-6

    def test_f_xy_product(self):
        """f(x,y) = x*y."""
        xs = [0., 1., 2., 3., 4.]
        ys = [0., 1., 2., 3., 4.]
        grid = [[xi*yj for yj in ys] for xi in xs]
        T, I = make_bi_table(xs, ys, grid)
        z, _ = biquad(T, I, 2.5, 1.5)
        assert abs(z - 3.75) < 1e-6


# ======================================================================
# UNINT tests
# ======================================================================

class TestUnint:
    XA = np.array([0., 1., 2., 3., 4.])
    YA = XA**2                            # f(x) = x²

    def test_linear_exact(self):
        """Linear function reproduced to machine precision."""
        ya = 2*self.XA + 1
        for x in [0.3, 1.0, 1.7, 2.5, 3.8]:
            y, l = unint(5, self.XA, ya, x)
            assert abs(y - (2*x+1)) < TOL_NUM and l == 0

    def test_quadratic_interior(self):
        for x, exp in [(0.5, 0.25), (1.5, 2.25), (2.5, 6.25), (3.5, 12.25)]:
            y, l = unint(5, self.XA, self.YA, x)
            assert abs(y - exp) < 1e-6

    def test_exact_knot(self):
        for xi, fi in zip(self.XA, self.YA):
            y, l = unint(5, self.XA, self.YA, xi)
            assert abs(y - fi) < TOL_NUM and l == 0

    def test_below_range(self):
        y, l = unint(5, self.XA, self.YA, -1.0)
        assert l == 1 and abs(y - 0.0) < TOL_NUM

    def test_above_range(self):
        y, l = unint(5, self.XA, self.YA, 10.0)
        assert l == 2 and abs(y - 16.0) < TOL_NUM

    def test_accepts_list(self):
        """unint must accept plain Python lists, not just np.ndarray."""
        xa = [0., 1., 2., 3., 4.]
        ya = [0., 1., 4., 9., 16.]
        y, l = unint(5, xa, ya, 2.5)
        assert abs(y - 6.25) < 1e-6

    def test_n_bounds_assertion(self):
        """N > len(XA) must raise AssertionError."""
        with pytest.raises(AssertionError):
            unint(10, self.XA, self.YA, 2.0)   # N=10 > len=5

    def test_partition_of_unity(self):
        ya = np.ones(5)
        for x in [0.5, 1.5, 2.5, 3.5]:
            y, _ = unint(5, self.XA, ya, x)
            assert abs(y - 1.0) < TOL_NUM


# ======================================================================
# WAIT tests
# ======================================================================

class TestWait:
    # Shared inputs
    kw = dict(ZMWT=0.3, BHP=500.0, DIA=8.0, AFT=125.0, BLADT=3.0, TIPSPD=850.0)

    def _ref(self, WTCON, **kw):
        """Pure-Python Fortran reference for any category."""
        ZND   = kw['TIPSPD'] * RPM_FROM_TIPSPD
        ZK2   = (kw['DIA'] / 10.0)**2
        ZK3   = (kw['BLADT'] / 4.0)**0.7
        ZK4   = kw['AFT'] / 100.0
        ZK5   = ZND / 20000.0
        ZK6   = (kw['BHP'] / 10.0 / kw['DIA']**2)**0.12
        ZK7   = (kw['ZMWT'] + 1.0)**0.5
        WTFAC = ZK2 * ZK3 * ZK6 * ZK7
        ZC    = 3.5 * ZK2 * kw['BLADT'] * ZK4**2 * (1.0/ZK5)**0.3
        if   WTCON == 1: return 170.0*WTFAC*ZK4**0.9*ZK5**0.35, 170.0*WTFAC*ZK4**0.9*ZK5**0.35
        elif WTCON == 2: return 200.0*WTFAC*ZK4**0.9*ZK5**0.35, 200.0*WTFAC*ZK4**0.9*ZK5**0.35
        elif WTCON == 3:
            w = 220.0*WTFAC*ZK4**0.7*ZK5**0.4 + ZC*(5.0/3.5)
            return w, w
        elif WTCON == 4:
            WTFAC2 = WTFAC * ZK4**0.7 * ZK5**0.4
            return 270.0*WTFAC2 + ZC*(5.0/3.5), 190.0*WTFAC2 + ZC
        elif WTCON == 5:
            return (220.0*WTFAC*ZK4**0.7*ZK5**0.4 + ZC*(5.0/3.5),
                    190.0*WTFAC*ZK4**0.7*ZK5**0.3)

    def test_all_categories(self):
        for cat in [1, 2, 3, 4, 5]:
            w70, w80 = wait(float(cat), **self.kw)
            r70, r80 = self._ref(cat, **self.kw)
            assert abs(w70 - r70) / r70 < TOL_REL, f"cat={cat} WT70"
            assert abs(w80 - r80) / r80 < TOL_REL, f"cat={cat} WT80"

    def test_wtcon_zero_returns_zeros(self):
        assert wait(0.0, **self.kw) == (0.0, 0.0)

    def test_wtcon_negative_returns_zeros(self):
        assert wait(-1.0, **self.kw) == (0.0, 0.0)

    def test_unknown_category_returns_zeros(self):
        w70, w80 = wait(9.0, **self.kw)
        assert w70 == 0.0 and w80 == 0.0


# ======================================================================
# COST tests
# ======================================================================

class TestCost:
    def _fresh(self):
        return (np.zeros((2, 11)), np.zeros(10), np.zeros(10))

    def test_ient1_default_factors(self):
        """IENT=1 with CLF1=0 → defaults 3.2178 / 1.02."""
        CQUAN, C70, C80 = self._fresh()
        CCLF1, CCLF, *_ = cost(3, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 500.0, 1,
                                CQUAN, 200.0, 150.0, C70, C80,
                                0.0, 0.0, 0.0, 0.0, IENT=1)
        assert abs(CCLF1 - 3.2178) < TOL_NUM
        assert abs(CCLF  - 1.02)   < TOL_NUM

    def test_ient1_user_factors(self):
        """IENT=1 with CLF1>0 → user values preserved."""
        CQUAN, C70, C80 = self._fresh()
        CCLF1, CCLF, *_ = cost(3, 3.0, 2.5, 1.05, 0.0, 0.0, 0.0, 500.0, 1,
                                CQUAN, 200.0, 150.0, C70, C80,
                                0.0, 0.0, 0.0, 0.0, IENT=1)
        assert abs(CCLF1 - 2.5)  < TOL_NUM
        assert abs(CCLF  - 1.05) < TOL_NUM

    def test_ient2_cost_arrays_filled(self):
        """IENT=2 → COST70 and COST80 filled for every quantity step."""
        CQUAN, C70, C80 = self._fresh()
        _, CCLF, CCK70, CCK80, CQUAN, C70, C80 = cost(
            3, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 500.0, 3,
            CQUAN, 200.0, 150.0, C70, C80, 3.2178, 1.02, 0.0, 0.0, IENT=2)
        assert all(C70[:3] > 0), "COST70 not filled"
        assert all(C80[:3] > 0), "COST80 not filled"
        assert all(C70[3:] == 0), "COST70 over-filled"

    def test_ient2_cquan_increments(self):
        """CQUAN steps by DAMT at each iteration."""
        CQUAN, C70, C80 = self._fresh()
        DAMT = 500.0; NAMT = 4
        cost(3, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, DAMT, NAMT,
             CQUAN, 200.0, 150.0, C70, C80, 3.2178, 1.02, 0.0, 0.0, IENT=2)
        for I in range(NAMT):
            assert abs(CQUAN[0, I+1] - (CQUAN[0, 0] + (I+1)*DAMT)) < TOL_NUM

    def test_zffac_layout(self):
        """Verify ZFFAC column-major transposition gives correct values."""
        from COST import _ZFFAC
        # Fortran DATA first 5 pairs: (1,1)=3.5,(2,1)=3.5,(1,2)=3.7,(2,2)=3.7,(1,3)=3.2
        assert abs(_ZFFAC[0, 0] - 3.5) < TOL_NUM   # ZFFAC(1,1)
        assert abs(_ZFFAC[1, 0] - 3.5) < TOL_NUM   # ZFFAC(2,1)
        assert abs(_ZFFAC[0, 1] - 3.7) < TOL_NUM   # ZFFAC(1,2)
        assert abs(_ZFFAC[1, 1] - 3.7) < TOL_NUM   # ZFFAC(2,2)
        assert abs(_ZFFAC[0, 4] - 2.0) < TOL_NUM   # ZFFAC(1,5)

    def test_zquan_layout(self):
        """Verify ZQUAN column-major transposition gives correct values."""
        from COST import _ZQUAN
        assert abs(_ZQUAN[0, 0] - 1910.) < TOL_NUM  # ZQUAN(1,1)
        assert abs(_ZQUAN[1, 0] - 2230.) < TOL_NUM  # ZQUAN(2,1)
        assert abs(_ZQUAN[0, 2] - 1030.) < TOL_NUM  # ZQUAN(1,3)
        assert abs(_ZQUAN[1, 4] - 368.)  < TOL_NUM  # ZQUAN(2,5)


# ======================================================================
# constants tests
# ======================================================================

class TestConstants:
    def test_rho_scale(self):
        """Fortran 10.E10 = 1×10^11."""
        assert RHO_SCALE == 1.0e11

    def test_rpm_factor(self):
        assert RPM_FACTOR == 6966.0

    def test_thrust_conv(self):
        assert THRUST_CONV == 364.76

    def test_thrust_denom(self):
        assert THRUST_DENOM == 1.515e6

    def test_speed_of_sound(self):
        assert SPEED_OF_SOUND == 1120.0

    def test_t0_isa(self):
        assert abs(T0_ISA - 518.688) < 1e-9

    def test_t_tropo(self):
        assert abs(T_TROPO - 389.988) < 1e-9

    def test_lapse_rate(self):
        assert abs(LAPSE_RATE - 0.00356) < 1e-9

    def test_rpm_from_tipspd(self):
        """60 / π to 5 significant figures."""
        assert abs(RPM_FROM_TIPSPD - 60.0/3.14159) < 1e-9

    def test_j_conv(self):
        assert J_CONV == 5.309

    def test_mach_ktas(self):
        assert abs(MACH_KTAS_FACTOR - 0.001512) < 1e-9

    def test_vk_conv(self):
        assert VK_CONV == 101.4

    def test_thrust_denom_rev(self):
        assert THRUST_DENOM_REV == 1.514e5


# ======================================================================
# OperatingCondition / PropellerGeometry validation tests
# ======================================================================

class TestOperatingCondition:
    def _valid_geom(self):
        return PropellerGeometry(D=8.0, DD=0.5, ND=3,
                                  AF=100.0, DAF=0.0, NAF=1,
                                  BLADN=3.0, DBLAD=0.0, NBL=1,
                                  CLII=0.5, DCLI=0.0, ZNCLI=1,
                                  ZMWT=0.3)

    def test_valid_iw1(self):
        c = OperatingCondition(IW=1, BHP=300.0, ALT=5000.0, VKTAS=120.0)
        c.validate()   # should not raise

    def test_valid_iw2(self):
        c = OperatingCondition(IW=2, THRUST=500.0, ALT=0.0, VKTAS=100.0)
        c.validate()

    def test_invalid_iw(self):
        with pytest.raises(ValueError, match="IW"):
            OperatingCondition(IW=4).validate()

    def test_iw1_requires_bhp(self):
        with pytest.raises(ValueError, match="BHP"):
            OperatingCondition(IW=1, BHP=0.0).validate()

    def test_iw2_requires_thrust(self):
        with pytest.raises(ValueError, match="THRUST"):
            OperatingCondition(IW=2, THRUST=0.0).validate()

    def test_alt_out_of_range(self):
        with pytest.raises(ValueError, match="ALT"):
            OperatingCondition(IW=1, BHP=100.0, ALT=200_000.0).validate()

    def test_negative_vktas(self):
        with pytest.raises(ValueError, match="VKTAS"):
            OperatingCondition(IW=1, BHP=100.0, VKTAS=-10.0).validate()

    def test_geometry_af_range(self):
        g = self._valid_geom(); g.AF = 50.0
        with pytest.raises(ValueError, match="AF"):
            g.validate()

    def test_geometry_bladn_range(self):
        g = self._valid_geom(); g.BLADN = 1.0
        with pytest.raises(ValueError, match="BLADN"):
            g.validate()

    def test_geometry_clii_range(self):
        g = self._valid_geom(); g.CLII = 0.9
        with pytest.raises(ValueError, match="CLII"):
            g.validate()

    def test_load_conditions_fills_state(self):
        """load_conditions must correctly populate PropellerState fields."""
        from MAIN import PropellerState
        st = PropellerState()
        geom = self._valid_geom()
        conds = [
            OperatingCondition(IW=1, BHP=300.0, ALT=5000.0, VKTAS=120.0,
                                TS=800.0, DTS=50.0, NDTS=3),
            OperatingCondition(IW=2, THRUST=400.0, ALT=0.0, VKTAS=80.0),
        ]
        load_conditions(conds, geom, st)
        assert st.NOF == 2
        assert st.IWIC[0] == 1 and st.IWIC[1] == 2
        assert abs(st.BHP[0]    - 300.0) < TOL_NUM
        assert abs(st.THRUST[1] - 400.0) < TOL_NUM
        assert abs(st.AF   - geom.AF)    < TOL_NUM
        assert abs(st.CLII - geom.CLII)  < TOL_NUM

    def test_load_conditions_too_many(self):
        geom  = self._valid_geom()
        conds = [OperatingCondition(IW=1, BHP=100.0)] * 11
        from MAIN import PropellerState
        with pytest.raises(ValueError, match="Maximum"):
            load_conditions(conds, geom, PropellerState())

    def test_load_conditions_empty(self):
        geom = self._valid_geom()
        from MAIN import PropellerState
        with pytest.raises(ValueError, match="least one"):
            load_conditions([], geom, PropellerState())


# ======================================================================
# ZNOISE table layout tests
# ======================================================================

class TestZnoiseTableLayout:
    def test_pnlc_shape(self):
        from ZNOISE import _PNLC
        assert _PNLC.shape == (13, 7, 4), f"Got {_PNLC.shape}"

    def test_pnlc_first_row_k0_i0(self):
        """PNLC[:,0,0] must match the first 13 values in the DATA statement."""
        from ZNOISE import _PNLC
        expected = [-2.5,-1.8,-1.0,0.0,0.8,1.4,1.8,2.0,2.25,2.75,3.5,4.3,5.3]
        assert np.allclose(_PNLC[:, 0, 0], expected)

    def test_pnlc_last_row_k3_i6(self):
        """PNLC[:,6,3] must match the last 13 values in the DATA statement."""
        from ZNOISE import _PNLC
        expected = [-5.0,-4.5,-3.7,-2.8,-2.3,-1.8,-1.4,-1.0,-0.7,-0.2,0.5,1.3,2.5]
        assert np.allclose(_PNLC[:, 6, 3], expected)


# ======================================================================
# PERFM table layout tests
# ======================================================================

class TestPerfmTableLayout:
    def test_cpang_shape(self):
        from PERFM import CPANG
        assert CPANG.shape == (10, 7, 4)

    def test_cpang_k0_l0(self):
        """CPANG[:,0,0] = first row of DATA (K=0, L=0, J=0.0 group)."""
        from PERFM import CPANG
        expected = [0.0158,0.0165,0.0188,0.0230,0.0369,0.0588,0.0914,0.1340,0.1816,0.2273]
        assert np.allclose(CPANG[:, 0, 0], expected)

    def test_cpang_k0_l1(self):
        """CPANG[:,0,1] = 8th row of DATA (K=0, L=1)."""
        from PERFM import CPANG
        expected = [0.0311,0.0320,0.0360,0.0434,0.0691,0.1074,0.1560,0.2249,0.3108,0.4026]
        assert np.allclose(CPANG[:, 0, 1], expected)

    def test_ctang_shape(self):
        from PERFM import CTANG
        assert CTANG.shape == (10, 7, 4)

    def test_bldang_shape(self):
        from PERFM import BLDANG
        assert BLDANG.shape == (7, 10)

    def test_bldang_k0(self):
        """BLDANG[0] = blade angles for J=0.0 group, INN[0]=10 values."""
        from PERFM import BLDANG
        expected = [0.,2.,4.,6.,10.,14.,18.,22.,26.,30.]
        assert np.allclose(BLDANG[0], expected)


# ======================================================================
# Entry point
# ======================================================================

if __name__ == '__main__':
    # Run with pytest
    sys.exit(pytest.main([__file__, '-v']))


# ======================================================================
# output.py tests
# ======================================================================

class TestOutputModule:
    def _make_summary(self):
        from output import RunSummary, ResultRow
        s = RunSummary(nof=1)
        s.rows = [
            ResultRow(condition=1, blades=3, af=100, cli=0.5,
                      dia_ft=8.0, tipspd_fps=850, cp=0.045, ct=0.08,
                      blade_ang=25.3, j=0.65, mach_tip=0.76, mach_fs=0.18,
                      thrust_lb=1200, shp=310, pnl_db=82.4,
                      wt70_lb=95.0, wt80_lb=78.0, cost70=4500, cost80=3800),
            ResultRow(condition=1, blades=3, af=100, cli=0.5,
                      dia_ft=8.0, tipspd_fps=900, off_chart=True),
        ]
        s.messages = ["Test message"]
        return s

    def test_csv_header_present(self):
        from output import ReportWriter
        s = self._make_summary()
        csv_text = ReportWriter(s).as_csv()
        assert "condition" in csv_text.splitlines()[0]

    def test_csv_row_count(self):
        from output import ReportWriter
        s = self._make_summary()
        lines = ReportWriter(s).as_csv().strip().splitlines()
        assert len(lines) == 3   # header + 2 data rows

    def test_json_round_trip(self):
        import json
        from output import ReportWriter
        s = self._make_summary()
        data = json.loads(ReportWriter(s).as_json())
        assert len(data["rows"]) == 2
        assert data["rows"][0]["dia_ft"] == 8.0
        assert data["rows"][1]["off_chart"] is True

    def test_text_contains_banner(self):
        from output import ReportWriter
        s = self._make_summary()
        txt = ReportWriter(s).as_text()
        assert "HAMILTON STANDARD" in txt

    def test_stdout_capture(self):
        from output import ResultsCollector
        col = ResultsCollector()
        with col.capture_stdout():
            print("hello from computation")
            print("second line")
        assert "hello from computation" in col.summary.messages
        assert "second line" in col.summary.messages

    def test_save_csv(self, tmp_path):
        from output import ReportWriter
        s = self._make_summary()
        p = tmp_path / "results.csv"
        ReportWriter(s).save_csv(p)
        assert p.exists()
        content = p.read_text()
        assert "condition" in content

    def test_save_all(self, tmp_path):
        from output import ReportWriter
        s = self._make_summary()
        saved = ReportWriter(s).save_all(tmp_path / "run1")
        for fmt in ("text", "csv", "json"):
            assert saved[fmt].exists(), f"{fmt} file not created"
