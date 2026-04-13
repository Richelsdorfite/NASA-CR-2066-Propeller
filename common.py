"""
common.py — Shared COMMON-block dataclasses (NASA CR-2066 propeller program)

These three classes replace the Fortran COMMON blocks /AFCOR/, /CPECTE/, and
/ASTRK/.  They are defined here — once — so that both MAIN.py and PERFM.py
import from the same source and work with the same instances, avoiding the
duplicate class definitions that existed in each file.
"""

from dataclasses import dataclass


@dataclass
class CommonAFCOR:
    """COMMON /AFCOR/ — Activity-factor correction factors set by PERFM."""
    AFCPE: float = 0.0   # AF correction on power coefficient
    AFCTE: float = 0.0   # AF correction on thrust coefficient
    XFT:   float = 0.0   # compressibility factor


@dataclass
class CommonCPECTE:
    """COMMON /CPECTE/ — Results written by PERFM, read by MAIN."""
    CPE:   float = 0.0   # power  coefficient result
    CTE:   float = 0.0   # thrust coefficient result
    BLLLL: float = 0.0   # blade angle result


@dataclass
class CommonASTRK:
    """COMMON /ASTRK/ — Sentinel values for off-chart conditions."""
    CPAST:  float = 0.0
    CTAST:  float = 0.0
    ASTERK: float = 999999.0   # flag value written to CP/CT when off chart
