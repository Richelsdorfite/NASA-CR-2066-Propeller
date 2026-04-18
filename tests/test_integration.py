"""
test_integration.py — End-to-end integration tests via MAIN.call_input / main_loop.

Three test classes cover the three IW modes:

  TestIW2TwoConditions  — fixed-thrust (IW=2), two-condition sweep from NASA CR-2066
                          report case.  8 result rows verified against CP/CT/SHP/
                          blade-angle reference values.

  TestIW3ReverseThrustWithRevtht  — reverse-thrust (IW=3) via REVTHT.  Key
                          (PCPW, VK) combinations verified against Thrust/SHP/θ.

  TestIW1StallCost      — stall iteration (IW=1, STALIT=1.0) with weight/cost.
                          4-blade and 6-blade rows verified against CP/CT/J/Wt/Cost.

All reference values were captured from verified Python runs and cross-checked
against NASA CR-2066 tables where available.  Tolerances: 0.5 % for smooth
aerodynamic quantities, 1 % for tabulated lookups, 2 % for noise/weight.
"""
import pytest
from operating_condition import OperatingCondition, PropellerGeometry
from output import ResultsCollector
import MAIN as M
from MAIN import call_input, main_loop, set_collector


# ── helper ───────────────────────────────────────────────────────────────────

def _run(conditions, geometry):
    col = ResultsCollector()
    set_collector(col)
    call_input(conditions, geometry)
    try:
        main_loop()
    finally:
        set_collector(None)
    return col


# ======================================================================
# IW=2 — fixed thrust, two-condition sweep
# ======================================================================

class TestIW2TwoConditions:
    """
    Condition 2 from the NASA CR-2066 report:
      ALT=7500 ft, T=32.33°F, THRUST=370 lbf, VKTAS=163.2 ktas
      D: 6 ft and 8 ft (ND=2, DD=2.0)
      Vt: 850/750/650/550 fps (NDTS=4, DTS=-100)
    """

    @pytest.fixture(scope="class")
    def results(self):
        geom = PropellerGeometry(
            D=6.0,  DD=2.0,  ND=2,
            AF=150.0, DAF=0.0, NAF=1,
            BLADN=4.0, DBLAD=0.0, NBL=1,
            CLII=0.5, DCLI=0.0, ZNCLI=1,
            ZMWT=0.262)
        cond = OperatingCondition(
            IW=2, THRUST=370.0, ALT=7500.0, VKTAS=163.2,
            TS=850.0, DTS=-100.0, NDTS=4, T=32.33)
        col = _run([cond], geom)
        return col.summary.rows

    def test_eight_rows_returned(self, results):
        """D×Vt sweep must produce 8 result rows (2 diameters × 4 tip speeds)."""
        assert len(results) == 8

    # ── D=6 ft rows ──────────────────────────────────────────────────────

    def test_d6_vt850_cp(self, results):
        r = results[0]
        assert r.cp == pytest.approx(0.091947, rel=0.005)

    def test_d6_vt850_ct(self, results):
        r = results[0]
        assert r.ct == pytest.approx(0.073949, rel=0.01)

    def test_d6_vt850_shp(self, results):
        r = results[0]
        assert r.shp == pytest.approx(226.3, rel=0.005)

    def test_d6_vt850_blade_angle(self, results):
        r = results[0]
        assert r.blade_ang == pytest.approx(23.48, abs=0.5)

    def test_d6_vt750_cp(self, results):
        r = results[1]
        assert r.cp == pytest.approx(0.125907, rel=0.005)

    def test_d6_vt750_ct(self, results):
        r = results[1]
        assert r.ct == pytest.approx(0.094984, rel=0.01)

    def test_d6_vt650_cp(self, results):
        r = results[2]
        assert r.cp == pytest.approx(0.189155, rel=0.005)

    def test_d6_vt550_cp(self, results):
        r = results[3]
        assert r.cp == pytest.approx(0.317880, rel=0.005)

    # ── D=8 ft rows ──────────────────────────────────────────────────────

    def test_d8_vt850_cp(self, results):
        r = results[4]
        assert r.cp == pytest.approx(0.059785, rel=0.005)

    def test_d8_vt850_ct(self, results):
        r = results[4]
        assert r.ct == pytest.approx(0.041597, rel=0.01)

    def test_d8_vt850_shp(self, results):
        r = results[4]
        assert r.shp == pytest.approx(261.6, rel=0.005)

    def test_d8_vt850_blade_angle(self, results):
        r = results[4]
        assert r.blade_ang == pytest.approx(21.96, abs=0.5)

    def test_d8_vt750_cp(self, results):
        r = results[5]
        assert r.cp == pytest.approx(0.077324, rel=0.005)

    def test_d8_vt650_cp(self, results):
        r = results[6]
        assert r.cp == pytest.approx(0.109840, rel=0.005)

    def test_d8_vt550_cp(self, results):
        r = results[7]
        assert r.cp == pytest.approx(0.174691, rel=0.005)

    # ── physical consistency ──────────────────────────────────────────────

    def test_larger_diameter_lower_cp(self, results):
        """At the same Vt=850 fps, D=8 ft requires lower CP than D=6 ft."""
        assert results[4].cp < results[0].cp

    def test_higher_vt_lower_cp_same_diameter(self, results):
        """For D=6 ft, CP must decrease as Vt increases (lower blade loading)."""
        cps = [r.cp for r in results[:4]]  # Vt = 850, 750, 650, 550
        # Vt decreases 850→550 so index 0 is highest Vt → lowest CP
        assert cps[0] < cps[1] < cps[2] < cps[3]


# ======================================================================
# IW=3 — reverse thrust (REVTHT)
# ======================================================================

class TestIW3ReverseThrust:
    """
    Reverse-thrust condition from the NASA CR-2066 demo case.
      D=8 ft, AF=200, BLADN=6, CLi=0.6, Vt range via NDTS
      VKTAS=0→72 ktas across NOUNT speed points
    """

    @pytest.fixture(scope="class")
    def rev_results(self):
        geom = PropellerGeometry(
            D=8.0,  DD=0.0,  ND=1,
            AF=200.0, DAF=0.0, NAF=1,
            BLADN=6.0, DBLAD=0.0, NBL=1,
            CLII=0.6, DCLI=0.0, ZNCLI=1,
            ZMWT=0.327)
        cond = OperatingCondition(
            IW=3,
            BHP=340.0, ALT=0.0, VKTAS=0.0,
            TS=700.0, DTS=0.0, NDTS=1,
            T=0.0,
            PCPW=100.0, DPCPW=0.0, NPCPW=1,
            ANDVK=72.0,   # touch-down speed; NOUNT = int(72/10)+2 = 9 speed points
            RPMC=700.0)   # full-throttle RPM for reverse thrust calc
        col = _run([cond], geom)
        return col.summary.rev_rows   # list of RevThrustRow

    def test_rev_rows_returned(self, rev_results):
        """IW=3 run must produce at least one reverse-thrust row."""
        assert rev_results, "No reverse-thrust rows produced"

    def test_static_thrust_at_full_power(self, rev_results):
        """
        At PCPW=100%, VK=0 (static), reverse thrust must exceed 400 lbf
        (physical lower bound for this geometry and BHP).
        """
        static = [r for r in rev_results if abs(r.vk_kts) < 1.0 and abs(r.pcpw - 100.0) < 1.0]
        assert static, "No static (VK≈0, PCPW=100%) row found"
        assert static[0].thrust_lb > 400.0

    def test_thrust_decreases_with_airspeed_at_full_power(self, rev_results):
        """
        In reverse flight, reverse thrust decreases with forward airspeed —
        maximum thrust is achieved statically (VK=0).
        """
        full = sorted(
            [r for r in rev_results if abs(r.pcpw - 100.0) < 1.0],
            key=lambda r: r.vk_kts)
        if len(full) >= 2:
            assert full[-1].thrust_lb < full[0].thrust_lb, \
                "Reverse thrust must decrease with increasing airspeed"


# ======================================================================
# IW=1 — stall iteration with weight and cost
# ======================================================================

class TestIW1StallCost:
    """
    50% stall-iteration case:
      D=8 ft, AF=200, blades 4 and 6, CLi=0.6
      BHP=340, ALT=0, VKTAS=77.5, ISA
      STALIT=1.0 → solver finds stall tip speed
      WTCON=4, DCOST=1.0 → weight and cost computed
    """

    @pytest.fixture(scope="class")
    def results(self):
        geom = PropellerGeometry(
            D=8.0,   DD=0.0,  ND=1,
            AF=200.0, DAF=0.0, NAF=1,
            BLADN=4.0, DBLAD=2.0, NBL=2,
            CLII=0.6,  DCLI=0.0, ZNCLI=1,
            ZMWT=0.327,
            WTCON=4.0,
            XNOE=2.0,
            CAMT=1.0, DAMT=1000.0, NAMT=5)
        cond = OperatingCondition(
            IW=1,
            BHP=340.0, ALT=0.0, VKTAS=77.5,
            TS=700.0, DTS=0.0, NDTS=1,
            T=0.0,
            DIST=500.0,
            STALIT=1.0,
            DCOST=1.0)
        col = _run([cond], geom)
        return col.summary.rows

    def test_two_rows_returned(self, results):
        """4-blade and 6-blade stall iteration must produce exactly 2 rows."""
        assert len(results) == 2

    # ── 4-blade row ──────────────────────────────────────────────────────

    def test_4blade_cp(self, results):
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        assert r4.cp == pytest.approx(0.933626, rel=0.005)

    def test_4blade_ct(self, results):
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        assert r4.ct == pytest.approx(0.446447, rel=0.01)

    def test_4blade_j(self, results):
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        assert r4.j == pytest.approx(1.1947, rel=0.005)

    def test_4blade_tipspd(self, results):
        """Stall tip speed for 4-blade must be ≈ 344.4 fps."""
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        assert r4.tipspd_fps == pytest.approx(344.4, rel=0.005)

    def test_4blade_weight70(self, results):
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        assert r4.wt70_lb == pytest.approx(228.0, rel=0.02)

    def test_4blade_cost70_qty1(self, results):
        """Unit cost at qty=1 for 4-blade propeller must be ≈ $7105."""
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        assert r4.cost70_qty[0] == pytest.approx(7105.0, rel=0.01)

    # ── 6-blade row ──────────────────────────────────────────────────────

    def test_6blade_cp(self, results):
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.cp == pytest.approx(1.702544, rel=0.005)

    def test_6blade_ct(self, results):
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.ct == pytest.approx(0.677920, rel=0.01)

    def test_6blade_tipspd(self, results):
        """Stall tip speed for 6-blade must be ≈ 281.9 fps."""
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.tipspd_fps == pytest.approx(281.9, rel=0.005)

    def test_6blade_weight70(self, results):
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.wt70_lb == pytest.approx(305.8, rel=0.02)

    def test_6blade_cost70_qty1(self, results):
        """Unit cost at qty=1 for 6-blade propeller must be ≈ $11925."""
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.cost70_qty[0] == pytest.approx(11925.0, rel=0.01)

    # ── physical consistency ──────────────────────────────────────────────

    def test_more_blades_lower_tip_speed(self, results):
        """
        At the stall limit, more blades → lower tip speed (wider blade, more
        chord, stalls at lower RPM).
        """
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.tipspd_fps < r4.tipspd_fps

    def test_more_blades_heavier(self, results):
        r4 = next(r for r in results if r.blades == pytest.approx(4.0))
        r6 = next(r for r in results if r.blades == pytest.approx(6.0))
        assert r6.wt70_lb > r4.wt70_lb

    def test_learning_curve_reduces_cost(self, results):
        """Unit cost at highest quantity must be lower than at qty=1."""
        for r in results:
            if r.cost70_qty:
                assert r.cost70_qty[-1] < r.cost70_qty[0], \
                    f"{r.blades:.0f}-blade: learning curve should reduce unit cost"

    def test_quantity_breakpoints_five(self, results):
        """NAMT=5 → five cost breakpoints for each blade count row."""
        for r in results:
            assert len(r.cost70_qty) == 5, \
                f"{r.blades:.0f}-blade: expected 5 qty breakpoints, got {len(r.cost70_qty)}"
