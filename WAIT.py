from constants import RPM_FROM_TIPSPD
import numpy as np
from typing import Tuple

def wait(WTCON: float, ZMWT: float, BHP: float, DIA: float,
         AFT: float, BLADT: float, TIPSPD: float) -> Tuple[float, float]:
    """
    Exact translation of SUBROUTINE WAIT (NASA CR-2066)
    Estimates propeller weight for 1970 (WT70) and 1980 (WT80) technology.
    
    If WTCON <= 0.0, returns (0.0, 0.0) immediately (no calculation).
    """

    if WTCON <= 0.0:
        return 0.0, 0.0

    # ------------------------------------------------------------------
    # Original Fortran calculations (lines 2-8)
    # ------------------------------------------------------------------
    ZND = TIPSPD * RPM_FROM_TIPSPD          # RPM
    ZN  = ZND / DIA                        # tip-speed parameter NOT USED IN THE CODE

    ZK2 = (DIA / 10.0) ** 2
    ZK3 = (BLADT / 4.0) ** 0.7
    ZK4 = AFT / 100.0
    ZK5 = ZND / 20000.0
    ZK6 = (BHP / 10.0 / DIA**2) ** 0.12
    ZK7 = (ZMWT + 1.0) ** 0.5

    WTFAC = ZK2 * ZK3 * ZK6 * ZK7

    # Category scaling term (used in categories 3, 4, 5)
    ZC = 3.5 * ZK2 * BLADT * ZK4**2 * (1.0 / ZK5)**0.3

    # ------------------------------------------------------------------
    # Branch on airplane category (IWTCON = int(WTCON))
    # ------------------------------------------------------------------
    IWTCON = int(WTCON)

    if IWTCON == 1:          # Category I
        WT70 = 170.0 * WTFAC * ZK4**0.9 * ZK5**0.35
        WT80 = WT70

    elif IWTCON == 2:        # Category II
        WT70 = 200.0 * WTFAC * ZK4**0.9 * ZK5**0.35
        WT80 = WT70

    elif IWTCON == 3:        # Category III
        WT70 = 220.0 * WTFAC * ZK4**0.7 * ZK5**0.4 + ZC * (5.0 / 3.5)
        WT80 = WT70

    elif IWTCON == 4:        # Category IV
        WTFAC = WTFAC * ZK4**0.7 * ZK5**0.4
        WT70 = 270.0 * WTFAC + ZC * (5.0 / 3.5)
        WT80 = 190.0 * WTFAC + ZC

    elif IWTCON == 5:        # Category V
        WT70 = 220.0 * WTFAC * ZK4**0.7 * ZK5**0.4 + ZC * (5.0 / 3.5)
        WT80 = 190.0 * WTFAC * ZK4**0.7 * ZK5**0.3

    else:
        # Unknown category → return zero weights (safety)
        WT70 = 0.0
        WT80 = 0.0

    return WT70, WT80