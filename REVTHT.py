import numpy as np
from typing import Tuple

from BIQUAD import biquad       # 4-point slope-continuous interpolation
from UNINT     import unint
from constants import RHO_SCALE, SPEED_OF_SOUND, VK_CONV, THRUST_DENOM_REV        # univariate slope-continuous interpolation

# ================================================================
# MODULE-LEVEL DATA TABLES (built once at import time)
# ================================================================

_TAFC = np.array([
    1.,7.,4.,80.,100.,120.,140.,160.,180.,200.,0.3,0.5,0.7,0.8,
    1.188,1.188,1.188,1.188,1.0,1.0,1.0,1.0,0.874,0.879,0.885,0.886,
    0.785,0.791,0.797,0.801,0.715,0.724,0.734,0.739,0.661,0.675,0.689,0.696,
    0.631,0.645,0.660,0.667
], dtype=float)

_QAFC = np.array([
    2.,7.,4.,80.,100.,120.,140.,160.,180.,200.,0.3,0.5,0.7,0.8,
    1.190,1.190,1.190,1.190,1.0,1.0,1.0,1.0,0.875,0.872,0.869,0.866,
    0.787,0.780,0.774,0.770,0.724,0.711,0.704,0.700,0.665,0.656,0.646,0.642,
    0.624,0.612,0.601,0.596
], dtype=float)

_DCQPPC = np.array([
    3.,6.,4.,0.,0.2,0.4,0.6,0.8,1.0,0.3,0.4,0.6,0.8,
    -0.0002,0.0,0.00048,0.00093,-0.0004,0.0,0.00081,0.00160,
    -0.0006,0.0,0.0012,0.0024,-0.00078,0.0,0.00158,0.00312,
    -0.00097,0.0,0.00194,0.00391,-0.00114,0.0,0.00231,0.00458
], dtype=float)

_PCCHC = np.array([
    5.,11.,14.,0.,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,
    -30.,-25.,-20.,-17.,-12.5,-8.8,-5.5,-2.3,1.5,5.0,8.5,11.9,15.,15.1,
    1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,
    0.875,0.875,0.925,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,
    0.750,0.750,0.791,0.849,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,
    0.623,0.623,0.660,0.708,0.828,1.,1.,1.,1.,1.,1.,1.,1.,1.,
    0.500,0.500,0.527,0.564,0.665,0.802,1.,1.,1.,1.,1.,1.,1.,1.,
    0.375,0.375,0.396,0.421,0.499,0.619,0.778,0.995,1.,1.,1.,1.,1.,1.,
    0.250,0.250,0.263,0.282,0.339,0.419,0.547,0.730,1.,1.,1.,1.,1.,1.,
    0.124,0.124,0.130,0.140,0.173,0.230,0.320,0.452,0.716,0.995,1.,1.,1.,1.,
    0.0,0.0,0.0,0.0,0.014,0.043,0.091,0.188,0.400,0.694,1.,1.,1.,1.,
    0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.095,0.375,0.695,1.,1.,1.,
    0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.350,0.685,0.998,1.
], dtype=float)

_CTPC = np.array([
    6.,6.,9.,0.,0.2,0.4,0.6,0.8,1.0,-30.,-25.,-20.,-15.,-10.,-5.,0.,5.,10.,
    -0.0955,-0.0855,-0.0700,-0.0498,-0.0262,-0.0005,0.0270,0.0590,0.1035,
    -0.1225,-0.1110,-0.0950,-0.0735,-0.0490,-0.0218,0.0060,0.0415,0.0840,
    -0.1590,-0.1440,-0.1265,-0.1040,-0.0785,-0.0505,-0.0215,0.0110,0.0500,
    -0.2080,-0.1895,-0.1715,-0.1490,-0.1230,-0.0965,-0.0700,-0.0340,0.0070,
    -0.2685,-0.2550,-0.2395,-0.2210,-0.2025,-0.1825,-0.1595,-0.1145,-0.0550,
    -0.3550,-0.3430,-0.3290,-0.3130,-0.2920,-0.2690,-0.2400,-0.1980,-0.1370
], dtype=float)

_TCPC = np.array([
    7.,9.,9.,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,-30.,-25.,-20.,-15.,-10.,-5.,0.,5.,10.,
    -0.077,-0.079,-0.080,-0.083,-0.081,-0.078,-0.0745,-0.071,-0.0675,
    -0.105,-0.109,-0.111,-0.1085,-0.104,-0.100,-0.095,-0.090,-0.0835,
    -0.142,-0.146,-0.148,-0.143,-0.1365,-0.1305,-0.1225,-0.112,-0.1035,
    -0.188,-0.188,-0.1865,-0.1825,-0.175,-0.165,-0.1535,-0.1385,-0.122,
    -0.228,-0.225,-0.222,-0.2185,-0.211,-0.198,-0.1815,-0.161,-0.1385,
    -0.261,-0.2585,-0.2545,-0.2485,-0.2395,-0.225,-0.205,-0.179,-0.148,
    -0.294,-0.288,-0.2815,-0.273,-0.261,-0.2445,-0.2225,-0.1895,-0.1495,
    -0.325,-0.316,-0.306,-0.294,-0.2775,-0.2585,-0.2345,-0.196,-0.147,
    -0.355,-0.343,-0.328,-0.3125,-0.292,-0.269,-0.240,-0.198,-0.137
], dtype=float)

_CQPC = np.array([
    8.,5.,9.,0.,0.4,0.6,0.8,1.0,-30.,-25.,-20.,-15.,-10.,-5.,0.,5.,10.,
    0.031,0.0241,0.0171,0.0108,0.0056,0.0022,0.0017,0.0028,0.0060,
    0.0363,0.0283,0.0201,0.0127,0.0064,0.0025,0.0014,0.0014,0.0035,
    0.0430,0.0330,0.0236,0.0150,0.0075,0.0027,0.0008,0.0005,0.0016,
    0.0523,0.0406,0.0289,0.0182,0.0091,0.0030,-0.0002,-0.0013,-0.0015,
    0.0629,0.0493,0.0346,0.0220,0.0110,0.0037,-0.0012,-0.0046,-0.0062
], dtype=float)

_QCPC = np.array([
    9.,5.,9.,0.2,0.4,0.6,0.8,1.0,-30.,-25.,-20.,-15.,-10.,-5.,0.,5.,10.,
    0.0107,0.0089,0.0068,0.0049,0.0030,0.0011,-0.0004,-0.0019,-0.0033,
    0.0202,0.0162,0.0122,0.0085,0.0049,0.0012,-0.0020,-0.0043,-0.0072,
    0.0353,0.0272,0.0195,0.0128,0.0070,0.0016,-0.0030,-0.0065,-0.0093,
    0.0491,0.0379,0.0278,0.0180,0.0091,0.0025,-0.0026,-0.0062,-0.0080,
    0.0629,0.0493,0.0346,0.0220,0.0110,0.0037,-0.0012,-0.0046,-0.0062
], dtype=float)

_CQPCZ = np.array([
    10.,8.,0.,0.0019,0.0028,0.0039,0.0056,0.0108,0.0171,0.0241,
    0.031,-3.5,-6.3,-7.9,-10.,-15.,-20.,-30.
], dtype=float)

_ASSJ = np.array([0.0, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00])


def _cbrt(x: float) -> float:
    """Cube root with sign (Fortran: ABS(X)**(1./3.)*X/ABS(X)), safe at x=0."""
    if x == 0.0:
        return 0.0
    return np.abs(x)**(1.0 / 3.0) * (x / np.abs(x))


def revtht(RTC: float, ROT: float, AFT: float, CLI: float, BLADN: float,
           DIA: float, CP: float, THETA: float, RORO: float,
           BHPI: float, RPMI: float, PCPWC: float, ANDVK: float) -> Tuple[float, float]:
    """
    Exact translation of SUBROUTINE REVTHT (NASA CR-2066)
    Computes reverse-thrust blade angle and full performance table.
    Prints the reverse-thrust table to console (matching original WRITE(6,...)).
    Returns (THETA, LIMIT) for compatibility with MAIN.
    """
    # ===================================================================
    # Main logic (exact Fortran flow)
    # ===================================================================

    LIMIT = 0

    # First two BIQUAD calls for activity factor corrections
    TAF, _ = biquad(_TAFC.tolist(), 0, AFT, CLI)
    QAF, _ = biquad(_QAFC.tolist(), 0, AFT, CLI)

    # RTC branch – solve for THETA or use supplied value
    if RTC == 1.0:
        # Compute reverse power coefficient
        CDPQ = CP / 6.2832 * (3.0 / BLADN)**0.83 * QAF
        DCQPP, _ = biquad(_DCQPPC.tolist(), 0, 0.0, CLI)   # static point
        CPQ = CDPQ - DCQPP
        THETA, _ = biquad(_CQPCZ.tolist(), 0, CPQ, 0.0)

    # Build performance table (I = 1 to 9)
    RPMC = np.zeros(9)
    BHPC = np.zeros(9)
    THRSTC = np.zeros(9)
    VKC = np.zeros(9)

    for I in range(5):                     # first 5 points (normal range)
        j = I
        CQP, _ = biquad(_CQPC.tolist(), 0, _ASSJ[j], THETA)
        CTP, _ = biquad(_CTPC.tolist(), 0, _ASSJ[j], THETA)
        PCCH, _ = biquad(_PCCHC.tolist(), 0, _ASSJ[j], THETA)
        if PCCH > 1.0:
            PCCH = 1.0
        DCQPP, _ = biquad(_DCQPPC.tolist(), 0, _ASSJ[j], CLI)
        DCTPP = 0.0975 * CLI - 0.039

        CP_val = (CQP + PCCH * DCQPP) * 6.2832 / (QAF * (3.0 / BLADN)**0.83)
        CT_val = (CTP + PCCH * DCTPP) / (TAF * (3.0 / BLADN)**0.83)

        if ROT != 1.0:                     # normal rotation case
            CONST = BHPI / RPMI * PCPWC / 100.0
            RPMC[I] = np.sqrt(RHO_SCALE * RORO * CONST / (2.0 * DIA**5 * CP_val))
            if RPMC[I] > RPMI and RTC != 2.0:
                RPMC[I] = RPMI
            BHPC[I] = CONST * RPMC[I]
        else:                              # special rotation case
            BHPC[I] = BHPI * PCPWC / 100.0
            CONST1 = RHO_SCALE * BHPC[I] * RORO / (2.0 * DIA**5 * CP_val)
            RPMC[I] = _cbrt(CONST1)

        VKC[I] = _ASSJ[j] * RPMC[I] * DIA / VK_CONV
        THRSTC[I] = CT_val * RPMC[I]**2 * DIA**4 / (THRUST_DENOM_REV * RORO)
        THRSTC[I] = abs(THRSTC[I])

    # Extended table for higher advance ratios (I = 6 to 9)
    # FIX 2: guard matches Fortran line 104: IF(VKC(5).GT.ANDVK) GO TO 90
    NNJ = 5
    if VKC[4] <= ANDVK:
        for I in range(5, 9):
            TJ = 1.0 / _ASSJ[I]
            QCP, _ = biquad(_QCPC.tolist(), 0, TJ, THETA)
            TCP, _ = biquad(_TCPC.tolist(), 0, TJ, THETA)
            CP_val = (QCP) * 6.2832 / (QAF * (3.0 / BLADN)**0.83) / TJ**2
            CT_val = (TCP) / (TAF * (3.0 / BLADN)**0.83) / TJ**2

            if ROT != 1.0:
                CONST = BHPI / RPMI * PCPWC / 100.0
                RPMC[I] = np.sqrt(RHO_SCALE * RORO * CONST / (2.0 * DIA**5 * CP_val))
                BHPC[I] = CONST * RPMC[I]
            else:
                BHPC[I] = BHPI * PCPWC / 100.0
                CONST1 = RHO_SCALE * BHPC[I] * RORO / (2.0 * DIA**5 * CP_val)
                RPMC[I] = _cbrt(CONST1)

            VKC[I] = DIA * RPMC[I] / (TJ * VK_CONV)
            THRSTC[I] = CT_val * RPMC[I]**2 * DIA**4 / (THRUST_DENOM_REV * RORO)
            THRSTC[I] = abs(THRSTC[I])
            # FIX 1: NNJ incremented BEFORE exit check (Fortran: NNJ=NNJ+1 then IF(VKC(I).GT.ANDVK))
            NNJ += 1
            if VKC[I] > ANDVK:
                break

    # ===================================================================
    # Final interpolated table output (matching Fortran WRITE statements)
    # ===================================================================
    NOUNT = int(ANDVK / 10.0) + 2
    TRIG = 0.0
    VK = 0.0

    print("\nREVERSE THRUST PERFORMANCE TABLE")
    print("DIA     PCPWC   THETA    VK     THRUST   SHP     RPM")

    for I in range(NOUNT):
        SHPV, _ = unint(NNJ, VKC[:NNJ], BHPC[:NNJ], VK)
        RPMV, _ = unint(NNJ, VKC[:NNJ], RPMC[:NNJ], VK)
        THRSTV, _ = unint(NNJ, VKC[:NNJ], THRSTC[:NNJ], VK)

        if SHPV > BHPI:
            SHPV = BHPI
        if RPMV > RPMI:
            RPMV = RPMI

        # FIX 3: column widths match Fortran FORMAT 92: F10.1,F9.0,F9.1,F8.1,F9.0,F8.0,F7.0
        if I == 0:
            print(f"{DIA:10.1f}{PCPWC:9.0f}{THETA:9.1f}{VK:8.1f}{THRSTV:9.0f}{SHPV:8.0f}{RPMV:7.0f}")
        else:
            # FIX 3: Fortran FORMAT 96: 2X,F8.1,F9.0,F8.0,F7.0
            print(f"  {VK:8.1f}{THRSTV:9.0f}{SHPV:8.0f}{RPMV:7.0f}")

        if TRIG == 1.0:
            break

        VK += 10.0
        if VK < ANDVK:
            continue
        VK = ANDVK
        TRIG = 1.0

    return THETA, LIMIT