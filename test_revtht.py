#!/usr/bin/env python
"""
test_revtht.py
--------------
Reverse thrust computation (IW=3) test case.

Operating condition
-------------------
  IW       = 3          Reverse thrust
  Engine   = ROT=1      Reciprocating
  RTC      = 1          Blade angle β₃/₄ computed from CP (not given)
  BHP      = 550 hp     Full throttle SHP
  RPMC     = 2200 RPM   Full throttle RPM
  ALT      = 0 ft       Sea level
  T        = 0          Standard ISA  (→ 518.69 °R ≈ 519 °R)
  ANDVK    = 72 kts     Touch-down speed
  PCPW     = 100 %      Starting power setting
  DPCPW    = -20 %      Power increment
  NPCPW    = 3          3 power steps  → 100 %, 80 %, 60 %

Propeller geometry
------------------
  D     = 8.50 ft       Diameter
  AF    = 109.0         Activity factor
  BLADN = 3             Blade count
  CLi   = 0.509         Integrated design CL
  ZMWT  = 0.3           Design flight Mach (not used in reverse thrust)
  RTC   = 1.0           Compute β from CP
  ROT   = 1.0           Reciprocating engine
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from MAIN import call_input, main_loop
from output import ResultsCollector
from operating_condition import OperatingCondition, PropellerGeometry
import MAIN as main_module

# ── Geometry ──────────────────────────────────────────────────────────────────
geometry = PropellerGeometry(
    D=8.50,  DD=0.0,  ND=1,          # one diameter: 8.50 ft
    AF=109.0, DAF=0.0, NAF=1,        # activity factor: 109
    BLADN=3.0, DBLAD=0.0, NBL=1,    # 3 blades only
    CLII=0.509, DCLI=0.0, ZNCLI=1,  # integrated design CL: 0.509
    ZMWT=0.3,                         # design flight Mach (informational)
    RTC=1.0,                          # compute β from CP
    ROT=1.0,                          # reciprocating engine
)

# ── Operating condition ───────────────────────────────────────────────────────
condition = OperatingCondition(
    IW=3,            # reverse thrust
    BHP=550.0,       # full-throttle SHP
    ALT=0.0,         # sea level
    VKTAS=0.0,       # not used in reverse thrust computation
    T=0.0,           # standard ISA temperature
    RPMC=2200.0,     # full-throttle RPM
    ANDVK=72.0,      # touch-down speed, knots
    PCPW=100.0,      # starting power setting, %
    DPCPW=-20.0,     # power-setting increment, %
    NPCPW=3,         # 3 power steps: 100 %, 80 %, 60 %
    BETA=0.0,        # blade angle (not used when RTC=1, computed by solver)
    # Tip-speed sweep fields are unused for IW=3
    TS=700.0, DTS=0.0, NDTS=1,
)

# ── Run ───────────────────────────────────────────────────────────────────────
print("=" * 72)
print("  REVERSE THRUST COMPUTATION  (IW=3)")
print("  Reciprocating engine  |  beta computed from CP  (RTC=1)")
print("  BHP=550  RPM=2200  Touch-down=72 kts  Power: 100 / 80 / 60 %")
print("  D=8.50 ft  AF=109  Blades=3  CLi=0.509")
print("=" * 72)

collector = ResultsCollector()
main_module.set_collector(collector)
call_input([condition], geometry)

try:
    main_loop()
finally:
    main_module.set_collector(None)

# ── Print captured solver output (the REVTHT table) ──────────────────────────
print()
for msg in collector.summary.messages:
    print(msg.encode(sys.stdout.encoding, errors='replace')
            .decode(sys.stdout.encoding))
