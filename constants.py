"""
constants.py — Named physical constants for the NASA CR-2066 propeller program.

These values appear across MAIN.py, PERFM.py, and REVTHT.py.  Centralising
them here means a single change propagates everywhere and eliminates the
risk of the same constant being spelled differently in different files
(e.g. 10.E10 vs 1e11 vs 10.0e10 all appeared in the original Fortran).
"""

# ── Power / thrust coefficient scaling ───────────────────────────────────
# Fortran: 10.E10 = 10.0 × 10^10 = 1.0 × 10^11
# Used in CP = BHP * RHO_SCALE / (2 * n^3 * D^5) and its inverse
RHO_SCALE: float = 1.0e11

# Shaft-power coefficient denominator (ft-lb/s unit conversion)
RPM_FACTOR: float = 6966.0

# Thrust coefficient conversion factor (knots / RPM / ft → dimensionless)
THRUST_CONV: float = 364.76

# Thrust coefficient denominator constant
THRUST_DENOM: float = 1.515e6   # used in CT → thrust (lbf) conversion in MAIN
THRUST_DENOM_REV: float = 1.514e5  # slightly different value used in REVTHT

# ── Atmosphere / speed ───────────────────────────────────────────────────
# Speed of sound at sea level, standard day (ft/s) used for Mach number
SPEED_OF_SOUND: float = 1120.0

# Knots → ft/s conversion  (1 knot = 1/0.5925 ft/s in the Fortran)
KNOTS_TO_FPS: float = 1.0 / 0.5925

# Advance ratio conversion  (J = V / (n*D), constant = 5.309 for VKTAS units)
J_CONV: float = 5.309

# Freestream Mach from VKTAS: ZMS[0] = 0.001512 * VKTAS * FC
MACH_KTAS_FACTOR: float = 0.001512

# Tip Mach from tip speed: ZMS[1] = TIPSPD * FC / 1120
MACH_TIP_FACTOR: float = 1.0 / SPEED_OF_SOUND

# ── Standard atmosphere reference ────────────────────────────────────────
T0_RANKINE: float = 518.69    # sea-level standard temperature (°R)
T0_ISA:     float = 518.688   # used in troposphere lapse rate formula
T_TROPO:    float = 389.988   # standard temperature above 36 000 ft (°R)
LAPSE_RATE: float = 0.00356   # °R per foot in troposphere
TROPO_ALT:  float = 36000.0   # tropopause altitude (ft)

# ── Propeller geometry ────────────────────────────────────────────────────
# RPM from tip speed: ZND = TIPSPD * 60 / π
RPM_FROM_TIPSPD: float = 60.0 / 3.14159

# Advance ratio denominator: VKC = ASSJ * RPM * D / 101.4
VK_CONV: float = 101.4
