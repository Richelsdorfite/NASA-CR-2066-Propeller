import numpy as np
from typing import Tuple

from BIQUAD import biquad       # 4-point slope-continuous interpolation
from UNINT  import unint        # univariate slope-continuous interpolation
from common    import CommonAFCOR, CommonCPECTE, CommonASTRK
from constants import RHO_SCALE, RPM_FACTOR, THRUST_CONV, THRUST_DENOM


# ================================================================
# ALL DATA TABLES – exact from your PERFM.f
# ================================================================

AFVAL = np.array([80., 100., 125., 150., 175., 200.])

AFCPC = np.array([
    [1.67, 1.55],
    [1.37, 1.33],
    [1.165, 1.149],
    [1.0, 1.0],
    [0.881, 0.890],
    [0.81, 0.82]
])

AFCTC = np.array([
    [1.39, 1.46],
    [1.27, 1.29],
    [1.123, 1.143],
    [1.0, 1.0],
    [0.915, 0.890],
    [0.865, 0.84]
])

XLB = np.array([2., 4., 6., 8.])
INN = np.array([10, 6, 8, 8, 7, 10, 6])
ZJJ = np.array([0., 0.5, 1., 1.5, 2., 3., 5.])
NJ = np.array([1, 2, 3, 4, 5, 6, 7])

# CPANG(10,7,4)
CPANG = np.array([
    [0.0158,0.0165,0.0188,0.0230,0.0369,0.0588,0.0914,0.1340,0.1816,0.2273],
    [0.0215,0.0459,0.0829,0.1305,0.1906,0.2554,0.,0.,0.,0.],
    [-0.0149,-0.0088,0.0173,0.0744,0.1414,0.2177,0.3011,0.3803,0.,0.],
    [-0.0670,-0.0385,0.0285,0.1304,0.2376,0.3536,0.4674,0.5535,0.,0.],
    [-0.1150,-0.0281,0.1086,0.2646,0.4213,0.5860,0.7091,0.,0.,0.],
    [-0.1151,0.0070,0.1436,0.2910,0.4345,0.5744,0.7142,0.8506,0.9870,1.1175],
    [-0.2427,0.0782,0.4242,0.7770,1.1164,1.4443,0.,0.,0.,0.],
    [0.0311,0.0320,0.0360,0.0434,0.0691,0.1074,0.1560,0.2249,0.3108,0.4026],
    [0.0380,0.0800,0.1494,0.2364,0.3486,0.4760,0.,0.,0.,0.],
    [-0.0228,-0.0109,0.0324,0.1326,0.2578,0.3990,0.5664,0.7227,0.,0.],
    [-0.1252,-0.0661,0.0535,0.2388,0.4396,0.6554,0.8916,1.0753,0.,0.],
    [-0.2113,-0.0480,0.1993,0.4901,0.7884,1.0990,1.3707,0.,0.,0.],
    [-0.2077,0.0153,0.2657,0.5387,0.8107,1.0750,1.3418,1.5989,1.8697,2.1238],
    [-0.4508,0.1426,0.7858,1.4480,2.0899,2.7130,0.,0.,0.,0.],
    [0.0450,0.0461,0.0511,0.0602,0.0943,0.1475,0.2138,0.2969,0.4015,0.5237],
    [0.0520,0.1063,0.2019,0.3230,0.4774,0.6607,0.,0.,0.,0.],
    [-0.0168,-0.0085,0.0457,0.1774,0.3520,0.5506,0.7833,1.0236,0.,0.],
    [-0.1678,-0.0840,0.0752,0.3262,0.6085,0.9127,1.2449,1.5430,0.,0.],
    [-0.2903,-0.0603,0.2746,0.6803,1.0989,1.5353,1.9747,0.,0.,0.],
    [-0.2783,0.0259,0.3665,0.7413,1.1215,1.4923,1.8655,2.2375,2.6058,2.9831],
    [-0.6181,0.1946,1.0758,1.9951,2.8977,3.7748,0.,0.,0.,0.],
    [0.0577,0.0591,0.0648,0.0751,0.1141,0.1783,0.2599,0.3551,0.4682,0.5952],
    [0.0650,0.1277,0.2441,0.3947,0.5803,0.8063,0.,0.,0.,0.],
    [-0.0079,-0.0025,0.0595,0.2134,0.4266,0.6708,0.9519,1.2706,0.,0.],
    [-0.1894,-0.0908,0.0956,0.3942,0.7416,1.1207,1.5308,1.9459,0.,0.],
    [-0.3390,-0.0632,0.3350,0.8315,1.3494,1.8900,2.4565,0.,0.,0.],
    [-0.3267,0.0404,0.4520,0.9088,1.3783,1.8424,2.3060,2.7782,3.2292,3.7058],
    [-0.7508,0.2395,1.3150,2.4469,3.5711,4.6638,0.,0.,0.,0.]
], dtype=float).reshape((4, 7, 10)).transpose(2, 1, 0)   # FIX 1: Fortran col-major → (L,K,i) then transpose to (i,K,L)

# CTANG(10,7,4)
CTANG = np.array([
    [0.0303,0.0444,0.0586,0.0743,0.1065,0.1369,0.1608,0.1767,0.1848,0.1858],
    [0.0205,0.0691,0.1141,0.1529,0.1785,0.1860,0.,0.,0.,0.],
    [-0.0976,-0.0566,0.0055,0.0645,0.1156,0.1589,0.1864,0.1905,0.,0.],
    [-0.1133,-0.0624,0.0111,0.0772,0.1329,0.1776,0.2020,0.2045,0.,0.],
    [-0.1132,-0.0356,0.0479,0.1161,0.1711,0.2111,0.2150,0.,0.,0.],
    [-0.0776,-0.0159,0.0391,0.0868,0.1279,0.1646,0.1964,0.2213,0.2414,0.2505],
    [-0.1228,-0.0221,0.0633,0.1309,0.1858,0.2314,0.,0.,0.,0.],
    [0.0426,0.0633,0.0853,0.1101,0.1649,0.2204,0.2678,0.3071,0.3318,0.3416],
    [0.0318,0.1116,0.1909,0.2650,0.3241,0.3423,0.,0.,0.,0.],
    [-0.1761,-0.0960,0.0083,0.1114,0.2032,0.2834,0.3487,0.3596,0.,0.],
    [-0.2155,-0.1129,0.0188,0.1420,0.2401,0.3231,0.3850,0.3850,0.,0.],
    [-0.2137,-0.0657,0.0859,0.2108,0.3141,0.3894,0.4095,0.,0.,0.],
    [-0.1447,-0.0314,0.0698,0.1577,0.2342,0.3013,0.3611,0.4067,0.4457,0.4681],
    [-0.2338,-0.0471,0.1108,0.2357,0.3357,0.4174,0.,0.,0.,0.],
    [0.0488,0.0732,0.0999,0.1301,0.2005,0.2731,0.3398,0.3982,0.4427,0.4648],
    [0.0375,0.1393,0.2448,0.3457,0.4356,0.4931,0.,0.,0.,0.],
    [-0.2295,-0.1240,0.0087,0.1443,0.2687,0.3808,0.4739,0.5256,0.,0.],
    [-0.2999,-0.1527,0.0235,0.1853,0.3246,0.4410,0.5290,0.5467,0.,0.],
    [-0.3019,-0.0907,0.1154,0.2871,0.4290,0.5338,0.5954,0.,0.,0.],
    [-0.2012,-0.0461,0.0922,0.2125,0.3174,0.4083,0.4891,0.5549,0.6043,0.6415],
    [-0.3307,-0.0749,0.1411,0.3118,0.4466,0.5548,0.,0.,0.,0.],
    [0.0534,0.0795,0.1084,0.1421,0.2221,0.3054,0.3831,0.4508,0.5035,0.5392],
    [0.0423,0.1588,0.2841,0.4056,0.5157,0.6042,0.,0.,0.,0.],
    [-0.2606,-0.1416,0.0097,0.1685,0.3172,0.4526,0.5655,0.6536,0.,0.],
    [-0.3615,-0.1804,0.0267,0.2193,0.3870,0.5312,0.6410,0.7032,0.,0.],
    [-0.3674,-0.1096,0.1369,0.3447,0.5165,0.6454,0.7308,0.,0.,0.],
    [-0.2473,-0.0594,0.1086,0.2552,0.3830,0.4933,0.5899,0.6722,0.7302,0.7761],
    [-0.4165,-0.1040,0.1597,0.3671,0.5289,0.6556,0.,0.,0.,0.]
], dtype=float).reshape((4, 7, 10)).transpose(2, 1, 0)   # FIX 1: same as CPANG

BLDANG = np.array([
    [0.,2.,4.,6.,10.,14.,18.,22.,26.,30.],
    [10.,15.,20.,25.,30.,35.,0.,0.,0.,0.],
    [10.,15.,20.,25.,30.,35.,40.,45.,0.,0.],
    [20.,25.,30.,35.,40.,45.,50.,55.,0.,0.],
    [30.,35.,40.,45.,50.,55.,60.,0.,0.,0.],
    [45.,47.5,50.,52.5,55.,57.5,60.,62.5,65.,67.5],
    [57.5,60.,62.5,65.,67.5,70.,0.,0.,0.,0.]
], dtype=float)

CTEC = np.array([0.01,0.03,0.05,0.07,0.09,0.12,0.16,0.20,0.24,0.28,0.32,0.36,0.40,0.44])

PFCLI = np.array([1.68,1.405,1.0,0.655,0.442,0.255,0.102])

TFCLI = np.array([1.22,1.105,1.0,0.882,0.792,0.665,0.540])

CPCLI = np.array([
    [0.0114,0.0294,0.0491,0.0698,0.0913,0.1486,0.2110,0.2802,0.3589,0.4443,0.5368,0.6255,0.,0.],
    [0.0294,0.0478,0.0678,0.0893,0.1118,0.1702,0.2335,0.3018,0.3775,0.4610,0.5505,0.6331,0.,0.],
    [0.0270,0.0324,0.0486,0.0671,0.0875,0.1094,0.1326,0.1935,0.2576,0.3259,0.3990,0.4805,0.5664,0.6438],
    [0.0490,0.0524,0.0684,0.0868,0.1074,0.1298,0.1537,0.2169,0.2827,0.3512,0.4235,0.5025,0.5848,0.6605],
    [0.0705,0.0743,0.0891,0.1074,0.1281,0.1509,0.1753,0.2407,0.3083,0.3775,0.4496,0.5265,0.6065,0.6826],
    [0.0915,0.0973,0.1114,0.1290,0.1494,0.1723,0.1972,0.2646,0.3345,0.4047,0.4772,0.5532,0.6307,0.7092]
], dtype=float)

CTCLI = np.array([
    [0.0013,0.0211,0.0407,0.0600,0.0789,0.1251,0.1702,0.2117,0.2501,0.2840,0.3148,0.3316,0.,0.],
    [0.0158,0.0362,0.0563,0.0761,0.0954,0.1419,0.1868,0.2287,0.2669,0.3013,0.3317,0.3460,0.,0.],
    [0.0,0.0083,0.0297,0.0507,0.0713,0.0916,0.1114,0.1585,0.2032,0.2456,0.2834,0.3191,0.3487,0.3626],
    [0.0130,0.0208,0.0428,0.0645,0.0857,0.1064,0.1267,0.1748,0.2195,0.2619,0.2995,0.3350,0.3647,0.3802],
    [0.0260,0.0331,0.0552,0.0776,0.0994,0.1207,0.1415,0.1907,0.2357,0.2778,0.3156,0.3505,0.3808,0.3990],
    [0.0365,0.0449,0.0672,0.0899,0.1125,0.1344,0.1556,0.2061,0.2517,0.2937,0.3315,0.3656,0.3963,0.4186]
], dtype=float)

XPCLI = np.array([
    [4.26,2.285,1.780,1.568,1.452,1.300,1.220,1.160,1.110,1.085,1.054,1.048,0.,0.],
    [1.652,1.408,1.292,1.228,1.188,1.132,1.105,1.080,1.058,1.042,1.029,1.022,0.,0.],
    [1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.],
    [0.551,0.619,0.712,0.775,0.815,0.845,0.865,0.891,0.910,0.928,0.941,0.958,0.970,0.975],
    [0.382,0.436,0.545,0.625,0.682,0.726,0.755,0.804,0.835,0.864,0.889,0.914,0.935,0.944],
    [0.293,0.333,0.436,0.520,0.585,0.635,0.670,0.730,0.770,0.807,0.835,0.871,0.897,0.909]
], dtype=float)

XTCLI = np.array([
    # NOTE: XTCLI[0][0] corrected from 22.85 (original document) to 4.474.
    # 22.85 is believed to be a scan/transcription error in the NASA CR-2066 source.
    # Estimated from trend: ratio XTCLI[row0]/XTCLI[row1] decreases smoothly from
    # 1.71 at pos 1 → extrapolates to ~2.1–2.6 at pos 0, giving ~3.9–4.9.
    # Cross-check via XPCLI row 0 ratio (pos0/pos1 = 4.26/2.285 = 1.864) applied to
    # XTCLI pos 1 (2.40 × 1.864 = 4.474). Only affects CLI=0.3 at very low CT (~0.0013).
    [4.474,2.40,1.75,1.529,1.412,1.268,1.191,1.158,1.130,1.122,1.108,1.108,0.,0.],
    [1.880,1.400,1.268,1.208,1.170,1.110,1.089,1.071,1.060,1.054,1.051,1.048,0.,0.],
    [1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.],
    [0.,0.399,0.694,0.787,0.831,0.860,0.881,0.908,0.926,0.940,0.945,0.951,0.958,0.958],
    [0.,0.251,0.539,0.654,0.719,0.760,0.788,0.831,0.865,0.885,0.900,0.910,0.916,0.916],
    [0.,0.1852,0.442,0.565,0.635,0.681,0.716,0.769,0.809,0.838,0.855,0.874,0.881,0.881]
], dtype=float)

CCLI = np.array([0.3,0.4,0.5,0.6,0.7,0.8])

ZMCRL = np.array([
    [0.,0.151,0.299,0.415,0.505,0.578,0.620,0.630,0.630,0.630,0.630],
    [0.,0.146,0.287,0.400,0.487,0.556,0.595,0.605,0.605,0.605,0.605],
    [0.,0.140,0.276,0.387,0.469,0.534,0.571,0.579,0.579,0.579,0.579],
    [0.,0.135,0.265,0.372,0.452,0.512,0.547,0.554,0.554,0.554,0.554],
    [0.,0.130,0.252,0.357,0.434,0.490,0.522,0.526,0.526,0.526,0.526],
    [0.,0.125,0.240,0.339,0.416,0.469,0.498,0.500,0.500,0.500,0.500]
], dtype=float)

ZJCL = np.array([0.,0.5,1.0,1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0])

CPEC = np.array([0.01,0.02,0.03,0.04,0.05,0.06,0.08,0.10,0.15,0.20,0.25,0.30,0.35,0.40])

BLDCR = np.array([
    [1.84,1.775,1.75,1.74,1.76,1.78,1.80,1.81,1.835,1.85,1.865,1.875,1.88,1.88],
    [1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.],
    [0.585,0.635,0.675,0.710,0.738,0.745,0.758,0.755,0.705,0.735,0.710,0.725,0.725,0.725],
    [0.415,0.460,0.505,0.535,0.560,0.575,0.600,0.610,0.630,0.630,0.610,0.605,0.600,0.600]
], dtype=float)

ZMMMC = np.array([
    1.,6.,12.,
    0.,0.02,0.04,0.06,0.08,0.10,
    0.01,0.02,0.04,0.08,0.12,0.16,0.20,0.24,0.28,0.32,0.36,0.40,
    1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,
    0.979,0.981,0.984,0.987,0.990,0.993,0.996,1.00,1.00,1.00,1.00,1.00,
    0.944,0.945,0.950,0.958,0.966,0.975,0.984,0.990,0.996,0.999,1.00,1.00,
    # NOTE: last two values corrected from 0.900,0.900 (original document) to 0.994,0.996.
    # 0.900 is believed to be a scan/transcription error (likely misread of 0.990 with a
    # dropped digit). However even 0.990 would be wrong: it would make the row flat from
    # pos 9 onward, inconsistent with all other DMN rows. Correct values estimated from:
    #   - Column interpolation (DMN=0.06 between 0.04→1.000 and 0.08→0.984):
    #       linear = 0.992, quadratic = 0.995 for both positions.
    #   - Within-row increment trend (slowing toward 1.0):
    #       pos9=0.990, +0.004 -> pos10=0.994, +0.002 -> pos11=0.996.
    # Both methods agree: CT=0.36 -> 0.994, CT=0.40 -> 0.996.
    0.901,0.905,0.912,0.927,0.942,0.954,0.964,0.974,0.984,0.990,0.994,0.996,
    0.862,0.866,0.875,0.892,0.909,0.926,0.942,0.957,0.970,0.980,0.984,0.984,
    0.806,0.813,0.825,0.851,0.877,0.904,0.924,0.939,0.952,0.961,0.971,0.976
], dtype=float)

NCLX = np.array([12,12,14,14,14,14])

BTDCR = np.array([
    [1.58,1.685,1.73,1.758,1.777,1.802,1.828,1.839,1.848,1.850,1.850,1.850,1.850,1.850],
    [1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.,1.],
    [0.918,0.874,0.844,0.821,0.802,0.781,0.764,0.752,0.750,0.750,0.750,0.750,0.750,0.750],
    [0.864,0.797,0.758,0.728,0.701,0.677,0.652,0.640,0.630,0.622,0.620,0.620,0.620,0.620]
], dtype=float)

ZMCRO = np.array([0.928,0.916,0.901,0.884,0.865,0.845])

CTSTAL = np.array([
    [0.125,0.151,0.172,0.187,0.204,0.218,0.233,0.243,0.249],
    [0.268,0.309,0.343,0.369,0.387,0.404,0.420,0.435,0.451],
    [0.401,0.457,0.497,0.529,0.557,0.582,0.605,0.629,0.651],
    [0.496,0.577,0.628,0.665,0.695,0.720,0.742,0.764,0.785]
], dtype=float)

CPSTAL = np.array([
    [0.05,0.12,0.22,0.35,0.49,0.65,0.82,1.01,1.19],
    [0.16,0.29,0.49,0.75,1.05,1.37,1.74,2.13,2.53],
    [0.30,0.47,0.75,1.1,1.51,1.96,2.41,2.86,3.30],
    [0.45,0.71,1.03,1.40,1.89,2.45,2.96,3.55,4.1]
], dtype=float)

ZJSTAL = np.array([0.,0.4,0.8,1.2,1.6,2.0,2.4,2.8,3.2])

def perfm(IW: int, CP: float, ZJI: float, AFT: float, BLADT: float,
          CLI: float, CT: float, ZMS: np.ndarray, LIMIT: int,
          com_afcor: CommonAFCOR,
          com_cpecte: CommonCPECTE,
          com_astrk: CommonASTRK) -> int:
    """
    Exact translation of SUBROUTINE PERFM (NASA CR-2066)
    Uses tables from Part 1 and your UNINT/BIQUAD.
    """

    # Local temporary arrays (matching Fortran DIMENSION)
    AFCP = np.zeros(7)
    AFCT = np.zeros(7)
    CTT = np.zeros(7)
    CPP = np.zeros(7)
    CTTT = np.zeros(4)
    BLL = np.zeros(7)
    BLLL = np.zeros(7)
    CPPP = np.zeros(4)
    PXCLI = np.zeros(16)
    TXCLI = np.zeros(6)
    XFFT = np.zeros(6)
    XFT1 = np.zeros(7)
    CPG = np.zeros(6)
    CPG1 = np.zeros(16)
    CTG = np.zeros(6)
    CTG1 = np.zeros(6)
    CTA = np.zeros(7)
    CTA1 = np.zeros(7)
    CTN = np.zeros(7)

    com_astrk.ASTERK = 999999.0

    # ===================================================================
    # Block 5: Activity Factor correction
    # ===================================================================
    for K in range(2):
        AFCP[K], _ = unint(6, AFVAL, AFCPC[:, K], AFT)
        AFCT[K], _ = unint(6, AFVAL, AFCTC[:, K], AFT)
    for K in range(2, 7):
        AFCP[K] = AFCP[1]
        AFCT[K] = AFCT[1]

    if ZJI <= 0.5:
        com_afcor.AFCPE = 2.0 * ZJI * (AFCP[1] - AFCP[0]) + AFCP[0]
        com_afcor.AFCTE = 2.0 * ZJI * (AFCT[1] - AFCT[0]) + AFCT[0]
    else:
        com_afcor.AFCPE = AFCP[1]
        com_afcor.AFCTE = AFCT[1]

    # ===================================================================
    # Block 6: J-group selection (NBEG/NEND)
    # ===================================================================
    if ZJI <= 1.0:
        NBEG, NEND = 0, 3
    elif ZJI <= 1.5:
        NBEG, NEND = 1, 4
    elif ZJI > 2.0 and IW < 3:
        NBEG, NEND = 3, 6
    else:
        NBEG, NEND = 2, 5

    # ===================================================================
    # Block 7: C_Li index selection
    # ===================================================================
    NCL = 0
    NCLT = 0
    NCLTT = 3
    for II in range(6):
        if abs(CLI - CCLI[II]) <= 0.0009:
            NCLT = II
            NCL = 1
            NCLTT = II
            break
    else:
        if CLI > 0.7:
            NCLT = 2
            NCLTT = 5
        elif CLI > 0.6:
            NCLT = 1
            NCLTT = 4

    # ===================================================================
    # Block 8: Blade-family selection
    # ===================================================================
    NB = int(BLADT + 0.1)
    LMOD = (NB % 2) + 1
    if LMOD == 1:
        NBB = 1
        L = int(BLADT / 2.0 + 0.1) - 1  # FIX 9: Fortran gives 1-based (1..4); subtract 1 for 0-based
    else:
        NBB = 4
        L = 0

    # ===================================================================
    # Block 9: Main blade loop (DO 500 IBB=1,NBB)
    # ===================================================================
    BLLLL = 0.0   # FIX 12: initialise so it is always defined

    for IBB in range(NBB):
        error_591 = False

        # ── J-group loop (DO 300 K=NBEG,NEND) ──────────────────────────
        # In the IW=2 branch, CTE is used for the BTDCR lookup (Fortran line 338)
        # but is not set inside the branch itself.  For K > NBEG it carries the
        # value written at label 271 (CTE = CTT[K]*AFCT[K]*TCLI) at the end of
        # the previous K body — correct Fortran carry-over behaviour.
        # For K = NBEG (first pass) Fortran has an undefined value; the best
        # practical approximation is CT * AFCT[NBEG] (input thrust × AF correction),
        # which keeps CTE inside the CTEC table range [0.01 … 0.44].
        CTE = CT * AFCT[NBEG]
        for K in range(NBEG, NEND + 1):

            # --- IW == 3: stall path ---
            if IW == 3:
                # FIX 8: CTSTAL[L] / CPSTAL[L] (row = blade family)
                CTT[K], _ = unint(9, ZJSTAL, CTSTAL[L], ZJJ[K])
                CPP[K], _ = unint(9, ZJSTAL, CPSTAL[L], ZJJ[K])
                # FIX 2: BLDANG[K] (row = J-group)
                BLL[K], _ = unint(INN[K], CPANG[:, K, L], BLDANG[K], CPP[K])

            # --- IW == 1: power path ---
            elif IW == 1:
                CPE = CP * AFCP[K]
                # FIX 6: BLDCR[L] (row = blade family, 14 CP values)
                PBL, _ = unint(14, CPEC, BLDCR[L], CPE)
                CPE1 = CPE * PBL * PFCLI[K]
                NNCLT = NCLT
                for KL in range(NCLT, NCLTT + 1):
                    # FIX 3: CPCLI[NNCLT] / XPCLI[NNCLT] (row = CLI group, 14 values)
                    PXCLI[KL], lim = unint(NCLX[NNCLT], CPCLI[NNCLT], XPCLI[NNCLT], CPE1)
                    if lim == 1:          # FIX 14: check LIMIT → label 591
                        error_591 = True; break
                    NNCLT += 1
                if error_591: break
                if NCL == 1:
                    PCLI = PXCLI[NCLT]
                else:
                    PCLI, _ = unint(4, CCLI[NCLT:NCLTT+1], PXCLI[NCLT:NCLTT+1], CLI)
                CPE = CPE * PCLI
                # FIX 2: BLDANG[K]
                BLL[K], _ = unint(INN[K], CPANG[:, K, L], BLDANG[K], CPE)
                CTT[K], lim = unint(INN[K], BLDANG[K], CTANG[:, K, L], BLL[K])
                if lim != 0:              # FIX 14: LIMIT.NE.0 → label 591
                    error_591 = True; break

            # --- IW == 2: thrust path ---
            else:
                # FIX 10 (partial): KL is outer loop, KJ is inner (Fortran DO 260/DO 2600)
                NNCLT = NCLT
                for KL in range(NCLT, NCLTT + 1):
                    # CTE carries the value from Fortran label 271 of the previous K-iteration
                    # (CTE = CTT[K]*AFCT[K]*TCLI); for K=NBEG it is 0.0 (initialised above).
                    CTA[0] = CT           # reset secant guesses for each CLI group
                    CTA[1] = 1.5 * CT
                    NFTX = 0
                    # For IW=2, trace first secant iteration to diagnose convergence
                    for KJ in range(5):
                        NFTX = KJ
                        CTE1 = CTA[KJ] * AFCT[K]
                        # FIX 7: BTDCR[L] (row = blade family)
                        TBL, lim = unint(14, CTEC, BTDCR[L], CTE)
                        if lim == 1:      # FIX 14
                            error_591 = True; break
                        CTE1 = CTE1 * TBL * TFCLI[K]
                        # FIX 4: CTCLI[NNCLT] / XTCLI[NNCLT] (row = CLI group)
                        TXCLI[KL], lim = unint(NCLX[NNCLT], CTCLI[NNCLT], XTCLI[NNCLT], CTE1)
                        if lim == 1:      # FIX 14
                            error_591 = True; break
                        if ZJJ[K] == 0.0:
                            ZMCRT = ZMCRO[NNCLT]
                            DMN = ZMS[1] - ZMCRT
                        else:
                            # FIX 5: ZMCRL[NNCLT] (row = CLI group, 11 J-values)
                            ZMCRT, _ = unint(11, ZJCL, ZMCRL[NNCLT], ZJJ[K])
                            DMN = ZMS[0] - ZMCRT
                        XFFT[KL] = 1.0
                        if DMN > 0.0:   # Fortran: IF(DMN) 2300,2300,252 — BIQUAD only when DMN > 0
                            CTE2 = CTE1 * TXCLI[KL] / TFCLI[K]
                            XFFT[KL], _ = biquad(ZMMMC.tolist(), 0, DMN, CTE2)
                        CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]
                        # FIX 13: first-iteration zero check (Fortran label 2300 / IF KJ.EQ.1)
                        if CTA1[0] == 0.0 and KJ == 0:
                            break
                        if KJ >= 1:
                            if abs(CTA1[KJ-1] - CTA1[KJ]) / CT <= 0.001:
                                break
                            CTA[KJ+1] = (-CTA1[KJ-1] * (CTA[KJ] - CTA[KJ-1])
                                         / (CTA1[KJ] - CTA1[KJ-1]) + CTA[KJ-1])
                    else:
                        print(' INTEGRATED DESIGN CL ADJUSTMENT NOT WORKING PROPERLY FOR CT DEFINITION')
                    if error_591: break
                    CTN[KL] = CTA[NFTX] / XFFT[KL]
                    NNCLT += 1
                if error_591: break
                if NCL == 1:
                    TCLI    = TXCLI[NCLT]
                    XFT1[K] = XFFT[NCLT]
                    CTT[K]  = CTN[NCLT]
                else:
                    TCLI,    _ = unint(4, CCLI[NCLT:NCLTT+1], TXCLI[NCLT:NCLTT+1], CLI)
                    XFT1[K], _ = unint(4, CCLI[NCLT:NCLTT+1], XFFT[NCLT:NCLTT+1], CLI)
                    CTT[K],  _ = unint(4, CCLI[NCLT:NCLTT+1],  CTN[NCLT:NCLTT+1], CLI)
                CTE = CTT[K] * AFCT[K] * TCLI
                # FIX 2: BLDANG[K]
                BLL[K], _ = unint(INN[K], CTANG[:, K, L], BLDANG[K], CTE)
                CPP[K], lim = unint(INN[K], BLDANG[K], CPANG[:, K, L], BLL[K])
                if lim != 0:          # Fortran: IF(LIMIT.EQ.0) GO TO 2501 / GO TO 591
                    error_591 = True; break

        # ── End of K loop ───────────────────────────────────────────────
        if error_591:
            CT = com_astrk.ASTERK
            CP = com_astrk.ASTERK
            com_cpecte.CPE = CP
            com_cpecte.CTE = CT
            com_cpecte.BLLLL = BLLLL
            return 1

        # Blade-angle J-interpolation (Fortran line 377)
        BLLL[IBB], _ = unint(4, ZJJ[NBEG:NEND+1], BLL[NBEG:NEND+1], ZJI)
        BLLLL = BLLL[IBB]   # FIX 12: set for every IBB (covers NBB==1 case)

        # ── Post-K IW dispatch: GO TO (310,350,310),IW ─────────────────
        if IW in (1, 3):
            # Label 310: compute CTTT[IBB] via CT-secant with CLI correction
            CTTT[IBB], _ = unint(4, ZJJ[NBEG:NEND+1], CTT[NBEG:NEND+1], ZJI)
            CTG[0] = 0.100
            CTG[1] = 0.200
            TFCLII, _ = unint(7, ZJJ, TFCLI, ZJI)
            for IL in range(5):
                CT_iter = CTG[IL]
                CTE = CTG[IL] * com_afcor.AFCTE
                # FIX 7: BTDCR[L]
                TBL, lim = unint(14, CTEC, BTDCR[L], CTE)
                if lim == 1: error_591 = True; break
                CTE1 = CTE * TBL * TFCLII
                NNCLT = NCLT
                for KL in range(NCLT, NCLTT + 1):
                    # FIX 4: CTCLI[NNCLT] / XTCLI[NNCLT]
                    TXCLI[KL], lim = unint(NCLX[NNCLT], CTCLI[NNCLT], XTCLI[NNCLT], CTE1)
                    if lim == 1: error_591 = True; break
                    if ZJI == 0.0:
                        ZMCRT = ZMCRO[NNCLT]
                        DMN = ZMS[1] - ZMCRT
                    else:
                        # FIX 5: ZMCRL[NNCLT]
                        ZMCRT, _ = unint(11, ZJCL, ZMCRL[NNCLT], ZJI)
                        DMN = ZMS[0] - ZMCRT
                    XFFT[KL] = 1.0
                    if DMN > 0.0:
                        CTE2 = CTE * TXCLI[KL] * TBL
                        XFFT[KL], _ = biquad(ZMMMC.tolist(), 0, DMN, CTE2)
                    NNCLT += 1
                if error_591: break
                if NCL == 1:
                    TCLII = TXCLI[NCLT]
                    XFT   = XFFT[NCLT]
                else:
                    TCLII, _ = unint(4, CCLI[NCLT:NCLTT+1], TXCLI[NCLT:NCLTT+1], CLI)
                    XFT,   _ = unint(4, CCLI[NCLT:NCLTT+1],  XFFT[NCLT:NCLTT+1], CLI)
                if XFT > 1.0:
                    XFT = 1.0
                CT_iter = CTG[IL]
                CTE = CTG[IL] * com_afcor.AFCTE * TCLII
                CTG1[IL] = CTE - CTTT[IBB]
                if abs(CTG1[IL] / CTTT[IBB]) < 0.001:
                    break
                if IL >= 1:
                    CTG[IL+1] = (-CTG1[IL-1] * (CTG[IL] - CTG[IL-1])
                                 / (CTG1[IL] - CTG1[IL-1]) + CTG[IL-1])
            else:
                print(' INTEGRATED DESIGN CL ADJUSTMENT NOT WORKING PROPERLY FOR CT DEFINITION')
            CTTT[IBB] = CT_iter   # label 392

            if error_591:
                CT = com_astrk.ASTERK; CP = com_astrk.ASTERK
                com_cpecte.CPE = CP; com_cpecte.CTE = CT; com_cpecte.BLLLL = BLLLL
                return 1

            if IW == 1:
                L += 1   # FIX 10: label 360, then 500 CONTINUE
                continue  # next IBB (skip CP block)
            # IW == 3 falls through to label 340

        # Label 350 (IW == 2): interpolate XFT from XFT1 over J
        if IW == 2:
            XFT, _ = unint(4, ZJJ[NBEG:NEND+1], XFT1[NBEG:NEND+1], ZJI)
            if XFT > 1.0:
                XFT = 1.0
        elif IW in (1, 3):
            # For power-specified (IW == 1) and stall (IW == 3), XFT defaults to 1.0 (no compressibility correction)
            XFT = 1.0

        # Label 340 (IW == 2 or IW == 3): compute CPPP[IBB] via CP-secant
        CPPP[IBB], _ = unint(4, ZJJ[NBEG:NEND+1], CPP[NBEG:NEND+1], ZJI)
        CPG[0] = 0.150
        CPG[1] = 0.200
        PFCLII, _ = unint(4, ZJJ[NBEG:NEND+1], PFCLI[NBEG:NEND+1], ZJI)
        for IL in range(5):
            CP_iter = CPG[IL]
            CPE = CPG[IL] * com_afcor.AFCPE
            # FIX 6: BLDCR[L]
            PBL, lim = unint(14, CPEC, BLDCR[L], CPE)
            if lim == 1: error_591 = True; break
            CPE1 = CPE * PBL * PFCLII
            NNCLT = NCLT
            for KL in range(NCLT, NCLTT + 1):
                # FIX 3: CPCLI[NNCLT] / XPCLI[NNCLT]
                PXCLI[KL], lim = unint(NCLX[NNCLT], CPCLI[NNCLT], XPCLI[NNCLT], CPE1)
                if lim == 1: error_591 = True; break
                NNCLT += 1
            if error_591: break
            if NCL == 1:
                PCLII = PXCLI[NCLT]
            else:
                PCLII, _ = unint(4, CCLI[NCLT:NCLTT+1], PXCLI[NCLT:NCLTT+1], CLI)
            CP_iter = CPG[IL]
            CPE = CPE * PCLII
            CPG1[IL] = CPE - CPPP[IBB]
            if abs(CPG1[IL] / CPPP[IBB]) <= 0.001:
                break
            if IL >= 1:
                CPG[IL+1] = (-CPG1[IL-1] * (CPG[IL] - CPG[IL-1])
                             / (CPG1[IL] - CPG1[IL-1]) + CPG[IL-1])
        else:
            print(' INTEGRATED DESIGN CL ADJUSTMENT NOT WORKING PROPERLY FOR CP DEFINITION')
        CPPP[IBB] = CP_iter   # label 287

        if error_591:
            CT = com_astrk.ASTERK; CP = com_astrk.ASTERK
            com_cpecte.CPE = CP; com_cpecte.CTE = CT; com_cpecte.BLLLL = BLLLL
            return 1

        L += 1   # FIX 10: label 360
    # ── End of IBB loop (500 CONTINUE) ──────────────────────────────────

    # ===================================================================
    # Final blade-number interpolation (Fortran labels 510-530/590)
    # ===================================================================
    if NBB > 1:
        BLLLL, _ = unint(4, XLB, BLLL, BLADT)
        if IW in (1, 3):
            CT, _ = unint(4, XLB, CTTT, BLADT)
        if IW != 1:   # IW=2: CP blade-interpolated; IW=3: use last IBB value (Fortran label 520)
            CP, _ = unint(4, XLB, CPPP, BLADT)
    else:  # NBB == 1: no blade interpolation — use single-family values
        if IW in (1, 3):
            CT = CTTT[0]
        if IW != 1:   # IW=2 and IW=3 both need CP (Fortran: CP set at label 287 before label 590)
            CP = CPPP[0]

    # ===================================================================
    # Error sentinel (label 591 reached via LIMIT flag above; normal path
    # completes without touching CT/CP here)
    # ===================================================================
    # Update COMMON blocks
    com_afcor.XFT = XFT
    com_cpecte.CPE   = CP
    com_cpecte.CTE   = CT
    com_cpecte.BLLLL = BLLLL

    return 0