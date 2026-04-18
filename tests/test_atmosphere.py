"""
test_atmosphere.py — Tests for atmosphere calculation and the T mutation fix.

Tests cover:
  - ISA temperature and density ratio at key altitudes
  - DT_ISA hot/cold day offset
  - T mutation regression: com_zinput.T[IC] must NOT be overwritten after a run
  - Repeated runs produce identical results (idempotency)
"""
import numpy as np
import pytest
from constants import T0_ISA, T_TROPO, LAPSE_RATE, T0_RANKINE
from UNINT import unint

_ALTPR  = np.array([0., 10000., 20000., 30000., 40000., 50000.,
                    60000., 70000., 80000., 90000., 100000.])
_PRESSR = np.array([1.0, 0.6877, 0.4595, 0.2970, 0.1851, 0.1145,
                    0.07078, 0.04419, 0.02741, 0.01699, 0.01054])


def _compute_atmosphere(alt_ft, T_user_f=0.0, dt_isa=0.0):
    """Mirror of the atmosphere block in main_loop(), returns (T_RANKINE, RORO, FC)."""
    if T_user_f <= 0.0:
        if alt_ft <= 36000.0:
            T_R = T0_ISA - LAPSE_RATE * alt_ft + dt_isa
        else:
            T_R = T_TROPO + dt_isa
    else:
        T_R = T_user_f + 459.69
    TOT  = T0_RANKINE / T_R
    FC   = float(np.sqrt(TOT))
    POP, _ = unint(11, _ALTPR, _PRESSR, alt_ft)
    RORO = 1.0 / (POP * TOT)
    return T_R, RORO, FC


class TestISAAtmosphere:

    def test_sea_level_temperature(self):
        """ISA sea-level temperature must be T0_ISA (≈ 518.688 °R)."""
        T_R, _, _ = _compute_atmosphere(0.0)
        assert T_R == pytest.approx(T0_ISA, rel=1e-5)

    def test_sea_level_density_ratio(self):
        """ISA sea-level density ratio must be 1.0."""
        _, RORO, _ = _compute_atmosphere(0.0)
        assert RORO == pytest.approx(1.0, rel=1e-4)

    def test_tropopause_temperature(self):
        """Above 36 000 ft the ISA temperature is constant at T_TROPO."""
        T_R, _, _ = _compute_atmosphere(40000.0)
        assert T_R == pytest.approx(T_TROPO, rel=1e-5)

    def test_density_decreases_with_altitude(self):
        """Air density must decrease monotonically with altitude."""
        roros = [_compute_atmosphere(alt)[1] for alt in [0, 5000, 10000, 30000]]
        for i in range(len(roros) - 1):
            assert roros[i] < roros[i + 1], \
                f"RORO should increase (ρ decreases) from alt {i*5000} to {(i+1)*5000}"

    def test_user_temperature_celsius_freezing(self):
        """T=32.33°F (≈ 0°C, near freezing) should convert to ≈ 492 °R."""
        T_R, _, _ = _compute_atmosphere(7500.0, T_user_f=32.33)
        assert T_R == pytest.approx(32.33 + 459.69, rel=1e-5)

    def test_hot_day_raises_temperature(self):
        """DT_ISA > 0 (hot day) must produce a higher T_RANKINE than standard ISA."""
        T_std,  _, _ = _compute_atmosphere(5000.0, dt_isa=0.0)
        T_hot,  _, _ = _compute_atmosphere(5000.0, dt_isa=+27.0)   # ISA+27°F
        T_cold, _, _ = _compute_atmosphere(5000.0, dt_isa=-27.0)   # ISA-27°F
        assert T_hot  > T_std
        assert T_cold < T_std
        assert T_hot  - T_std  == pytest.approx(27.0, abs=0.01)
        assert T_std  - T_cold == pytest.approx(27.0, abs=0.01)

    def test_dt_isa_ignored_for_user_specified_temperature(self):
        """
        When T > 0 (user-specified), DT_ISA is NOT applied.
        Two calls with different dt_isa must return the same T_RANKINE.
        """
        T1, _, _ = _compute_atmosphere(5000.0, T_user_f=50.0, dt_isa=0.0)
        T2, _, _ = _compute_atmosphere(5000.0, T_user_f=50.0, dt_isa=30.0)
        assert T1 == pytest.approx(T2, rel=1e-10)


class TestTMutationFix:
    """
    Regression tests for the T mutation bug (fixed in this codebase).

    The bug: after the first run, com_zinput.T[IC] was overwritten with the
    Rankine value. On a second run the conversion +459.69 was applied again,
    producing a wrong temperature. The fix uses a local T_RANKINE variable.
    """

    def _run(self, conditions, geometry):
        from MAIN import call_input, main_loop, set_collector
        from output import ResultsCollector
        import MAIN as M
        col = ResultsCollector()
        set_collector(col)
        call_input(conditions, geometry)
        try:
            main_loop()
        finally:
            set_collector(None)
        return col

    def test_T_field_not_mutated_after_run(self):
        """
        After main_loop(), the user-supplied T[IC] must still hold the
        original °F value (32.33), not the converted Rankine value.
        """
        from operating_condition import OperatingCondition, PropellerGeometry
        from MAIN import state

        geom = PropellerGeometry(
            D=6.0, DD=0.0, ND=1, AF=150.0, DAF=0.0, NAF=1,
            BLADN=4.0, DBLAD=0.0, NBL=1, CLII=0.5, DCLI=0.0, ZNCLI=1,
            ZMWT=0.262)
        cond = OperatingCondition(
            IW=2, THRUST=370.0, ALT=7500.0, VKTAS=163.2,
            TS=850.0, DTS=0.0, NDTS=1, T=32.33)

        self._run([cond], geom)
        # state.T[0] is populated by load_conditions from cond.T
        assert state.T[0] == pytest.approx(32.33, abs=0.01), \
            "T[IC] must NOT be overwritten with Rankine value"

    def test_repeated_runs_produce_identical_results(self):
        """
        Running the same computation twice must yield bit-identical CP and CT.
        If T were mutated the second run would use a wrong temperature.
        """
        from operating_condition import OperatingCondition, PropellerGeometry

        geom = PropellerGeometry(
            D=6.0, DD=0.0, ND=1, AF=150.0, DAF=0.0, NAF=1,
            BLADN=4.0, DBLAD=0.0, NBL=1, CLII=0.5, DCLI=0.0, ZNCLI=1,
            ZMWT=0.262)
        cond = OperatingCondition(
            IW=2, THRUST=370.0, ALT=7500.0, VKTAS=163.2,
            TS=850.0, DTS=0.0, NDTS=1, T=32.33)

        col1 = self._run([cond], geom)
        col2 = self._run([cond], geom)

        assert col1.summary.rows, "Run 1 produced no results"
        assert col2.summary.rows, "Run 2 produced no results"
        r1, r2 = col1.summary.rows[0], col2.summary.rows[0]
        assert r1.cp == pytest.approx(r2.cp, rel=1e-9), "CP must be identical on repeat run"
        assert r1.ct == pytest.approx(r2.ct, rel=1e-9), "CT must be identical on repeat run"
