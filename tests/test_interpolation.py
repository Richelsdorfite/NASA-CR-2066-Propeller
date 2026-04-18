"""
test_interpolation.py — Unit tests for UNINT and BIQUAD.

UNINT  : slope-continuous univariate interpolation.
BIQUAD : slope-continuous bivariate (or univariate) interpolation.
Both are direct translations of the Fortran IV routines in NASA CR-2066.
"""
import numpy as np
import pytest
from UNINT import unint
from BIQUAD import biquad

# ── ALTPR / PRESSR table used throughout atmosphere calculations ───────────
_ALTPR  = np.array([0., 10000., 20000., 30000., 40000., 50000.,
                    60000., 70000., 80000., 90000., 100000.])
_PRESSR = np.array([1.0, 0.6877, 0.4595, 0.2970, 0.1851, 0.1145,
                    0.07078, 0.04419, 0.02741, 0.01699, 0.01054])


# ======================================================================
# UNINT
# ======================================================================

class TestUNINT:

    def test_at_first_knot(self):
        """Exact value at the lowest table entry."""
        y, L = unint(11, _ALTPR, _PRESSR, 0.0)
        assert y == pytest.approx(1.0)
        assert L == 0

    def test_at_interior_knot(self):
        """Exact value at an interior knot point (no interpolation needed)."""
        y, L = unint(11, _ALTPR, _PRESSR, 10000.0)
        assert y == pytest.approx(0.6877)
        assert L == 0

    def test_at_last_knot(self):
        """Exact value at the highest table entry."""
        y, L = unint(11, _ALTPR, _PRESSR, 100000.0)
        assert y == pytest.approx(0.01054)
        assert L == 0

    def test_below_range_returns_first_value(self):
        """Below the table minimum: returns the first entry and sets L=1."""
        y, L = unint(11, _ALTPR, _PRESSR, -500.0)
        assert y == pytest.approx(1.0)
        assert L == 1

    def test_above_range_returns_last_value(self):
        """Above the table maximum: returns the last entry and sets L=2."""
        y, L = unint(11, _ALTPR, _PRESSR, 150000.0)
        assert y == pytest.approx(0.01054)
        assert L == 2

    def test_interpolated_midpoint(self):
        """
        At 5 000 ft the interpolated pressure ratio should fall strictly
        between the 0-ft and 10 000-ft values.
        Regression value 0.833338 captured from the running code.
        """
        y, L = unint(11, _ALTPR, _PRESSR, 5000.0)
        assert L == 0
        assert 0.6877 < y < 1.0
        assert y == pytest.approx(0.833338, rel=1e-4)

    def test_tropopause_altitude(self):
        """
        At 36 000 ft (ISA tropopause) pressure ratio regression value 0.224458.
        Ensures the interpolation passes correctly through the knee.
        """
        y, L = unint(11, _ALTPR, _PRESSR, 36000.0)
        assert L == 0
        assert y == pytest.approx(0.224458, rel=1e-4)

    def test_small_table(self):
        """Minimal 4-point linear table: exact recovery at all knots.
        Note: UNINT requires at least 4 points for its slope-estimation stencil.
        """
        xa = np.array([0.0, 1.0, 2.0, 3.0])
        ya = np.array([0.0, 5.0, 10.0, 15.0])
        for x, expected in [(0.0, 0.0), (1.0, 5.0), (2.0, 10.0), (3.0, 15.0)]:
            y, L = unint(4, xa, ya, x)
            assert y == pytest.approx(expected), f"x={x}"
            assert L == 0

    def test_linear_function_exact(self):
        """
        Slope-continuous interpolation is exact for linear functions.
        f(x) = 3x + 1, tested at a non-knot interior point.
        """
        xa = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        ya = 3.0 * xa + 1.0
        y, L = unint(5, xa, ya, 1.7)
        assert y == pytest.approx(3.0 * 1.7 + 1.0, rel=1e-6)
        assert L == 0


# ======================================================================
# BIQUAD
# ======================================================================

def _make_univariate_table(xs, ys):
    """
    Pack xs and ys into the BIQUAD table format (univariate, NY=0).
    T = [0., NX, 0., x0, x1, ..., y0, y1, ...]
    The leading 0. is a dummy (T[I] is never read; I=0, so NX is at T[1]).
    """
    NX = len(xs)
    T = [0.0, float(NX), 0.0] + list(xs) + list(ys)
    return T


class TestBIQUAD:

    def test_univariate_exact_at_knot(self):
        """Value at an interior knot is returned exactly."""
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [0.0, 2.0, 4.0, 6.0, 8.0]
        T = _make_univariate_table(xs, ys)
        z, K = biquad(T, 0, 2.0, 0.0)
        assert z == pytest.approx(4.0, abs=1e-9)
        assert K == 0

    def test_univariate_linear_midpoint(self):
        """
        For a linear function, slope-continuous cubic interpolation is exact
        at any interior query point.
        f(x) = 2x, queried at x = 1.5.
        """
        xs = [0.0, 1.0, 2.0, 3.0]
        ys = [0.0, 2.0, 4.0, 6.0]
        T = _make_univariate_table(xs, ys)
        z, K = biquad(T, 0, 1.5, 0.0)
        assert z == pytest.approx(3.0, abs=1e-9)
        assert K == 0

    def test_univariate_below_range(self):
        """Query below the X range clamps to the first Y value; K=1."""
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 20.0, 30.0, 40.0]
        T = _make_univariate_table(xs, ys)
        z, K = biquad(T, 0, 0.0, 0.0)
        assert K == 1
        assert z == pytest.approx(10.0, abs=1e-9)

    def test_univariate_above_range(self):
        """Query above the X range clamps to the last Y value; K=2."""
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 20.0, 30.0, 40.0]
        T = _make_univariate_table(xs, ys)
        z, K = biquad(T, 0, 99.0, 0.0)
        assert K == 2
        assert z == pytest.approx(40.0, abs=1e-9)

    def test_zmmmc_table_known_point(self):
        """
        Regression test using the actual ZMMMC Mach-correction table from
        PERFM.py.  At DMN=0.04, CTE2=0.20 (interior bivariate point) the
        result must match the value captured from a known-good run.
        Expected value 0.984000 confirmed from code run.
        """
        from PERFM import ZMMMC
        z, K = biquad(ZMMMC.tolist(), 0, 0.04, 0.20)
        assert K == 0
        assert z == pytest.approx(0.984, abs=5e-4)
