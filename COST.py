import numpy as np
from typing import Tuple, List

# ================================================================
# MODULE-LEVEL DATA TABLES (built once at import time)
# ================================================================

# ZFFAC(2,5): column-major DATA → .reshape(5,2).T
# Row 0 = ZFFAC(1,*): 1970 technology cost factors by airplane category
# Row 1 = ZFFAC(2,*): 1980 technology cost factors by airplane category
_ZFFAC = np.array([3.5, 3.5, 3.7, 3.7, 3.2, 3.2, 2.6, 3.5, 2.0, 3.4],
                  dtype=float).reshape(5, 2).T

# ZEFAC(5): 1D – 1980 extra cost factor per category
_ZEFAC = np.array([1.0, 1.5, 3.5, 3.5, 3.5], dtype=float)

# ZQUAN(2,5): column-major DATA → .reshape(5,2).T
# Row 0 = ZQUAN(1,*): 1970 reference production quantities by category
# Row 1 = ZQUAN(2,*): 1980 reference production quantities by category
_ZQUAN = np.array([1910., 2230., 2810., 5470., 1030.,
                   1990.,  295.,  680.,   65.,  368.],
                  dtype=float).reshape(5, 2).T

def cost(WTCON: float, BLADT: float, CLF1: float, CLF: float,
         CK70: float, CK80: float, CAMT: float, DAMT: float, NAMT: int,
         CQUAN: np.ndarray,
         WT70: float, WT80: float,
         COST70: np.ndarray, COST80: np.ndarray,
         CCLF1: float, CCLF: float, CCK70: float, CCK80: float,
         IENT: int) -> Tuple[float, float, float, float, np.ndarray, np.ndarray, np.ndarray]:
    """
    Exact translation of SUBROUTINE COST (NASA CR-2066)
    Computes propeller manufacturing cost for 1970 and 1980 technology
    using learning-curve economics.

    FIX 3: IENT controls the two-phase call protocol (matching Fortran GO TO (5,100), IENT):
        IENT=1 → initialise CCLF1/CCLF only, then return immediately (label 5 → 1000)
        IENT=2 → compute CCK70, CCK80, CQUAN, COST70(I), COST80(I)  (label 100)

    FIX 4/5: COST70(10), COST80(10) and CQUAN(2,11) are in/out arrays, passed
             in and updated in-place (matching the Fortran DIMENSION interface).

    Returns:
        (CCLF1, CCLF, CCK70, CCK80, CQUAN, COST70, COST80)
    """

    # ===================================================================
    # ICON — airplane category index (1-based)
    # ===================================================================
    ICON = int(WTCON + 0.01)

    # ===================================================================
    # IENT dispatch — GO TO (5, 100), IENT
    # ===================================================================

    if IENT == 1:
        if CLF1 <= 0.0:
            CCLF1 = 3.2178
            CCLF  = 1.02
        else:
            CCLF1 = CLF1
            CCLF  = CLF
        return CCLF1, CCLF, CCK70, CCK80, CQUAN, COST70, COST80

    # CCK70
    if CK70 <= 0.0:
        CCK70 = _ZFFAC[0, ICON-1] * (3.0 * BLADT**0.75 + _ZEFAC[ICON-1])
    else:
        CCK70 = CK70

    # CCK80
    if CK80 <= 0.0:
        CCK80 = _ZFFAC[1, ICON-1] * (3.0 * BLADT**0.75 + _ZEFAC[ICON-1])
    else:
        CCK80 = CK80

    # CQUAN initial values
    if CAMT <= 0.0:
        CQUAN[0, 0] = _ZQUAN[0, ICON-1]
        CQUAN[1, 0] = _ZQUAN[1, ICON-1]
    else:
        CQUAN[0, 0] = CAMT
        CQUAN[1, 0] = CAMT

    # Learning-curve exponent
    XLN = (np.log(CCLF) - np.log(CCLF1)) / 6.90775527

    # ── DO 200 I=1,NAMT ──────────────────────────────────────────────────
    # FIX 4: fill COST70(I) and COST80(I) for every quantity step
    for I in range(NAMT):
        COST70[I] = CCK70 * np.exp(np.log(CQUAN[0, I]) * XLN + np.log(CCLF1)) * WT70 / CCLF1
        COST80[I] = CCK80 * np.exp(np.log(CQUAN[1, I]) * XLN + np.log(CCLF1)) * WT80 / CCLF1
        CQUAN[0, I+1] = CQUAN[0, I] + DAMT   # CQUAN(1,I+1) = CQUAN(1,I) + DAMT
        CQUAN[1, I+1] = CQUAN[1, I] + DAMT   # CQUAN(2,I+1) = CQUAN(2,I) + DAMT

    return CCLF1, CCLF, CCK70, CCK80, CQUAN, COST70, COST80