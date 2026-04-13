# ============================================================
# BIQUAD – corrected translation of Fortran IV (NASA CR-2066)
# ============================================================

def biquad(T: list[float], I: int, XI: float, YI: float) -> tuple[float, int]:
    """
    Parameters
    ----------
    T  : packed table (0-based list)
    I  : starting index of the table entry in T
    XI : X query value
    YI : Y query value (ignored / set 0.0 for univariate tables)

    Returns
    -------
    Z : interpolated value
    K : status flag  0=normal, 1=below X range, 2=above X range,
                     3=below Y range, 6=above Y range  (bivariate K = Kx + 3*Ky)
    """
    NX = int(T[I + 1])
    NY = int(T[I + 2])
    J1 = I + 3           # index of first X knot
    J2 = J1 + NX - 1    # index of last  X knot

    # --- Search in X ---
    KX, JX1, RA, RB, X_cl = _search(T, J1, J2, XI)
    K   = KX
    JX  = JX1            # save stencil start (Fortran: JX = JX1 at label 100)

    # Fill XC with the 4 surrounding X-knots (Fortran labels 105-110)
    XC = [T[JX1 + j] for j in range(4)]

    # Compute interpolation coefficients in X  (Fortran label 2000)
    C = _coeffs(XC, X_cl, RA, RB)

    # ---- UNIVARIATE (NY == 0) ----
    if NY == 0:
        # Function values start at J2+1; the stencil offset is JX-J1
        # so JY = JX + NX  (Fortran label 210)
        JY = JX + NX
        Z  = sum(C[j] * T[JY + j] for j in range(4))
        return Z, K

    # ---- BIVARIATE ----
    J1_y = J2 + 1          # first Y knot index
    J2_y = J1_y + NY - 1   # last  Y knot index

    # Search in Y (Fortran label 1000 re-entered with L=1)
    KY, JX1_y, RA_y, RB_y, Y_cl = _search(T, J1_y, J2_y, YI)
    K = K + 3 * KY          # Fortran label 500

    # For each of the 4 Y-stencil positions, interpolate in X
    # Base index (Fortran label 500):
    #   JY = J2+1 + (JX - I - 3)*NY + JX1-J1
    # In our notation (J2→J2_y, J1→J1_y, JX1→JX1_y):
    base = J2_y + 1 + (JX - I - 3) * NY + (JX1_y - J1_y)

    Y = [0.0] * 4
    for M in range(4):                         # Fortran DO 550
        jx_inner = base + M                    # = JY for this M
        val = 0.0
        for j in range(4):                     # Fortran DO 520
            val += C[j] * T[jx_inner + j * NY]
        Y[M] = val

    # Compute Y-direction coefficients (Fortran labels 105→2000)
    XC_y = [T[JX1_y + j] for j in range(4)]
    C_y  = _coeffs(XC_y, Y_cl, RA_y, RB_y)

    # Final interpolation  (Fortran label 600)
    Z = sum(C_y[j] * Y[j] for j in range(4))
    return Z, K


# ------------------------------------------------------------------ #
#  Internal helpers                                                    #
# ------------------------------------------------------------------ #

def _search(T: list[float], J1: int, J2: int, X: float):
    """
    Search routine (Fortran labels 1000-1600).
    Returns (KX, JX1, RA, RB, X_clamped).
    """
    KX      = 0
    X_cl    = X

    for J in range(J1, J2 + 1):
        if T[J] - X >= 0.0:
            break
    else:
        # Off high end – Fortran falls through to X=T(J2), KX=2, then 1020
        X_cl = T[J2]
        return 2, J2 - 3, 0.0, 1.0, X_cl

    diff = J - J1 - 1

    if diff < 0:
        # Off low end (or exact hit at first knot) – labels 1080/1082/1090
        if T[J] - X != 0.0:          # strictly below: label 1082
            KX   = 1
            X_cl = T[J1]
        return KX, J1, 1.0, 0.0, X_cl

    if diff == 0:
        # First interval – label 1090 (RA=1, no clamping)
        return 0, J1, 1.0, 0.0, X_cl

    # diff > 0 – label 1100
    if J == J2:
        # Last interval treated like off-high-end tail: label 1020
        # NOTE: no X clamping here (Fortran jumps INTO 1020, after X=T(J2))
        return 0, J2 - 3, 0.0, 1.0, X_cl

    # Normal interior interval – label 1500
    RA = (T[J] - X) / (T[J] - T[J - 1])
    return 0, J - 2, RA, 1.0 - RA, X_cl


def _coeffs(XC: list[float], X: float, RA: float, RB: float) -> list[float]:
    """
    Coefficient routine (Fortran label 2000).
    Uses EQUIVALENCE XC↔D: P from knot differences, D from X distances.
    Returns C[0..3].
    """
    P = [0.0] * 5
    for j in range(3):
        P[j] = XC[j + 1] - XC[j]
    P[3] = P[0] + P[1]   # Fortran P(4)
    P[4] = P[1] + P[2]   # Fortran P(5)

    D = [X - XC[j] for j in range(4)]

    C = [0.0] * 4
    C[0] = ( RA / P[0]) * (D[1] / P[3]) *  D[2]
    C[1] = (-RA / P[0]) * (D[0] / P[1]) *  D[2] + (RB / P[1]) * (D[2] / P[4]) * D[3]
    C[2] = ( RA / P[1]) * (D[0] / P[3]) *  D[1] - (RB / P[1]) * (D[1] / P[2]) * D[3]
    C[3] = ( RB / P[4]) * (D[1] / P[2]) *  D[2]
    return C