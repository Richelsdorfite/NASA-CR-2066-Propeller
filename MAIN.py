import numpy as np
from dataclasses import dataclass, field
from typing import List

from BIQUAD import biquad
from UNINT  import unint
from PERFM  import perfm
from ZNOISE import znoise
from WAIT   import wait
from COST   import cost
from REVTHT import revtht
from common    import CommonAFCOR, CommonCPECTE, CommonASTRK
from constants import (RHO_SCALE, RPM_FACTOR, THRUST_CONV, THRUST_DENOM,
                        SPEED_OF_SOUND, J_CONV, MACH_KTAS_FACTOR,
                        T0_RANKINE, T0_ISA, T_TROPO, LAPSE_RATE, TROPO_ALT,
                        RPM_FROM_TIPSPD)
from units import FT_TO_M, FPS_TO_MS, HP_TO_KW, LBF_TO_N, LB_TO_KG, FTLBF_TO_NM
from operating_condition import (OperatingCondition, PropellerGeometry,
                                  load_conditions)

# ===================================================================
# BLOCK 1: Single program-state dataclass
# ===================================================================

@dataclass
class PropellerState:
    """
    Replaces all four Fortran COMMON blocks and the module-level work arrays.

    Sections
    --------
    /AFCOR/   – activity-factor correction factors (written by PERFM, read by MAIN)
    /CPECTE/  – CP/CT/blade-angle results         (written by PERFM, read by MAIN)
    /ASTRK/   – sentinel values for off-chart conditions
    /ZINPUT/  – all user-supplied operating-condition data (filled by HMI / call_input)
    Work arrays – FC, RORO, ZMS, CQUAN, COST70, COST80, BHPG, THRSTG, TIPSDG
    """

    # ── /AFCOR/ ──────────────────────────────────────────────────────
    AFCPE:  float = 0.0
    AFCTE:  float = 0.0
    XFT:    float = 0.0

    # ── /CPECTE/ ─────────────────────────────────────────────────────
    CPE:    float = 0.0
    CTE:    float = 0.0
    BLLLL:  float = 0.0

    # ── /ASTRK/ ──────────────────────────────────────────────────────
    CPAST:  float = 0.0
    CTAST:  float = 0.0
    ASTERK: float = 999999.0

    # ── /ZINPUT/ scalars ─────────────────────────────────────────────
    NOF:    int   = 0
    D:      float = 0.0
    DD:     float = 0.0
    ND:     int   = 0
    AF:     float = 0.0
    DAF:    float = 0.0
    NAF:    int   = 0
    BLADN:  float = 0.0
    DBLAD:  float = 0.0
    NBL:    int   = 0
    XNOE:   float = 0.0
    WTCON:  float = 0.0
    ZMWT:   float = 0.0
    CLF1:   float = 0.0
    CLF:    float = 0.0
    CK70:   float = 0.0
    CK80:   float = 0.0
    CAMT:   float = 0.0
    DAMT:   float = 0.0
    NAMT:   int   = 0
    CLII:   float = 0.0
    DCLI:   float = 0.0
    ZNCLI:  int   = 0
    RTC:    float = 0.0
    ROT:    float = 0.0

    # ── /ZINPUT/ per-condition arrays (max 10 operating conditions) ──
    BHP:    List[float] = field(default_factory=lambda: [0.0] * 10)
    THRUST: List[float] = field(default_factory=lambda: [0.0] * 10)
    ALT:    List[float] = field(default_factory=lambda: [0.0] * 10)
    VKTAS:  List[float] = field(default_factory=lambda: [0.0] * 10)
    T:      List[float] = field(default_factory=lambda: [0.0] * 10)
    DT_ISA: List[float] = field(default_factory=lambda: [0.0] * 10)  # ISA deviation °F/°R
    TS:     List[float] = field(default_factory=lambda: [0.0] * 10)
    IWIC:   List[int]   = field(default_factory=lambda: [0]   * 10)
    DTS:    List[float] = field(default_factory=lambda: [0.0] * 10)
    NDTS:   List[int]   = field(default_factory=lambda: [1]   * 10)  # ← default 1 step, not 0
    DIST:   List[float] = field(default_factory=lambda: [0.0] * 10)
    STALIT: List[float] = field(default_factory=lambda: [0.0] * 10)
    DCOST:  List[float] = field(default_factory=lambda: [0.0] * 10)
    PCPW:   List[float] = field(default_factory=lambda: [0.0] * 10)
    NPCPW:  List[int]   = field(default_factory=lambda: [0]   * 10)
    BETA:   List[float] = field(default_factory=lambda: [0.0] * 10)
    DPCPW:  List[float] = field(default_factory=lambda: [0.0] * 10)
    RPMC:   List[float] = field(default_factory=lambda: [0.0] * 10)
    ANDVK:  List[float] = field(default_factory=lambda: [0.0] * 10)

    # ── Work arrays ──────────────────────────────────────────────────
    FC:     np.ndarray = field(default_factory=lambda: np.zeros(10))
    RORO:   np.ndarray = field(default_factory=lambda: np.zeros(10))
    ZMS:    np.ndarray = field(default_factory=lambda: np.zeros(2))
    CQUAN:  np.ndarray = field(default_factory=lambda: np.zeros((2, 11)))
    COST70: np.ndarray = field(default_factory=lambda: np.zeros(10))
    COST80: np.ndarray = field(default_factory=lambda: np.zeros(10))
    BHPG:   np.ndarray = field(default_factory=lambda: np.zeros(10))
    THRSTG: np.ndarray = field(default_factory=lambda: np.zeros(10))
    TIPSDG: np.ndarray = field(default_factory=lambda: np.zeros(11))

    def as_afcor(self) -> CommonAFCOR:
        """Return a CommonAFCOR view (for passing to perfm/revtht)."""
        obj = CommonAFCOR()
        obj.AFCPE = self.AFCPE; obj.AFCTE = self.AFCTE; obj.XFT = self.XFT
        return obj

    def as_cpecte(self) -> CommonCPECTE:
        """Return a CommonCPECTE view (for passing to perfm)."""
        obj = CommonCPECTE()
        obj.CPE = self.CPE; obj.CTE = self.CTE; obj.BLLLL = self.BLLLL
        return obj

    def as_astrk(self) -> CommonASTRK:
        """Return a CommonASTRK view (for passing to perfm)."""
        obj = CommonASTRK()
        obj.CPAST = self.CPAST; obj.CTAST = self.CTAST; obj.ASTERK = self.ASTERK
        return obj

    def sync_from_perfm(self, afcor: CommonAFCOR, cpecte: CommonCPECTE,
                        astrk: CommonASTRK) -> None:
        """Pull PERFM results back into the state object after each call."""
        self.AFCPE  = afcor.AFCPE;   self.AFCTE  = afcor.AFCTE
        self.XFT    = afcor.XFT
        self.CPE    = cpecte.CPE;    self.CTE    = cpecte.CTE
        self.BLLLL  = cpecte.BLLLL
        self.ASTERK = astrk.ASTERK


# Single global program state – replaces com_afcor, com_astrk, com_cpecte,
# com_zinput and the module-level work arrays
state = PropellerState()

# ── Convenience aliases so the rest of the code reads clearly ────────────
# These let existing code like com_zinput.BHP[IC] keep working without a
# global search-and-replace.  They are just names pointing at the same object.
com_zinput = state    # /ZINPUT/ fields live on state
com_afcor  = state    # /AFCOR/  fields live on state
com_cpecte = state    # /CPECTE/ fields live on state
com_astrk  = state    # /ASTRK/  fields live on state

# ── Results collector hook ────────────────────────────────────────────────
# Use set_collector() to attach / detach a ResultsCollector.
# Leave as None for command-line / plain-text use.
_collector = None   # type: ignore

# Unit system for log/display output.  Set to "SI" by HMI.py before calling
# main_loop() when the user has selected SI units.  The computation itself
# always runs in US customary units; only the log lines are converted.
_unit_system: str = "US"


def _emit(text: str) -> None:
    """Send a message to the active collector (HMI) or stdout (CLI)."""
    if _collector is not None:
        _collector.add_message(text)
    else:
        print(text)


def set_collector(collector) -> None:
    """Attach (or detach when None) a ResultsCollector for the current run.

    Also wires up the message emitters in PERFM and REVTHT so that their
    diagnostic prints reach the same destination without redirecting stdout.
    """
    global _collector
    import PERFM, REVTHT
    _collector = collector
    emitter = collector.add_message if collector is not None else print
    PERFM._emit_fn  = emitter
    REVTHT._emit_fn = emitter
# Allows RORO[IC], FC[IC] etc. without changing any loop body.
FC     = state.FC
RORO   = state.RORO
ZMS    = state.ZMS
CQUAN  = state.CQUAN
COST70 = state.COST70
COST80 = state.COST80
BHPG   = state.BHPG
THRSTG = state.THRSTG
TIPSDG = state.TIPSDG

# ===================================================================
# BLOCK 2: DATA statements and statement function
# ===================================================================

ALTPR = np.array([0., 10000., 20000., 30000., 40000., 50000.,
                  60000., 70000., 80000., 90000., 100000.])

PRESSR = np.array([1.0, 0.6877, 0.4595, 0.2970, 0.1851, 0.1145,
                   0.07078, 0.04419, 0.02741, 0.01699, 0.01054])


def CBRT(x: float) -> float:
    """Cube-root, equivalent of Fortran CBRT(X) = X**(1./3.)"""
    return float(np.cbrt(x))

# ===================================================================
# BLOCK 3: Header print + CALL INPUT
# ===================================================================

def call_input(conditions: List[OperatingCondition],
               geometry:   PropellerGeometry) -> None:
    """
    Replaces the Fortran CALL INPUT / perf-card reader.

    The HMI builds a list of OperatingCondition objects and one
    PropellerGeometry object, then calls this function once before
    calling main_loop().  All fields are validated before the state
    is modified.

    Example
    -------
    >>> from operating_condition import OperatingCondition, PropellerGeometry
    >>> geom = PropellerGeometry(D=8.0, DD=0.5, ND=3,
    ...                          AF=100.0, DAF=0.0, NAF=1,
    ...                          BLADN=3.0, DBLAD=0.0, NBL=1,
    ...                          CLII=0.5, DCLI=0.0, ZNCLI=1,
    ...                          ZMWT=0.3)
    >>> conds = [OperatingCondition(IW=1, BHP=300.0, ALT=0.0, VKTAS=120.0,
    ...                              TS=800.0, DTS=50.0, NDTS=5)]
    >>> call_input(conds, geom)
    >>> main_loop()
    """
    load_conditions(conditions, geometry, state)


def print_header():
    """Prints the exact same banner as the original Fortran program"""
    _emit("\n" + "="*80)
    _emit(" " * 19 + "HAMILTON STANDARD COMPUTER DECK NO. H432")
    _emit(" " * 17 + "COMPUTES PERFORMANCE, NOISE, WEIGHT, AND COST FOR")
    _emit(" " * 26 + "GENERAL AVIATION PROPELLERS")
    _emit("="*80 + "\n")


# ======================  MAIN EXECUTION STARTS HERE  ======================
if __name__ == "__main__":
    print_header()          # Equivalent to WRITE (6,1)
    
    # CALL INPUT  →  We will translate INPUT.f in the next step
    # For now we call a placeholder function that will be filled later
    call_input()            # This will become the full INPUT logic
 
 # ===================================================================
# BLOCK 4: Main operating condition loop (DO 700 IC=1,NOF)
#          + density ratio calculation
# ===================================================================

def main_loop():
    """Main operating condition loop – equivalent to DO 700 IC=1,NOF"""
    
    for IC in range(int(com_zinput.NOF)):          # IC: 0-based (Fortran IC was 1-based)
        
        # NCOST = DCOST(IC) + .01
        NCOST = int(com_zinput.DCOST[IC] + 0.01)
        
        # Special handling for 50% stall tipspeed option
        if com_zinput.STALIT[IC] > 0.50:
            com_zinput.NDTS[IC] = 10
            com_zinput.DTS[IC]  = 0.0
        
        # Select computation mode
        IW = int(com_zinput.IWIC[IC])
        
        # IW error check
        if IW > 3:
            _emit(f"INPUT ERROR, IW= {IW} IC= {IC+1}")
            continue
        
        # ===================================================================
        # DENSITY RATIO CALCULATION (lines ~100–180)
        # ===================================================================
        
        # Temperature handling – T_RANKINE is local; com_zinput.T[IC] (user's
        # °F input) is never overwritten so repeated Run clicks stay correct.
        temp_f = com_zinput.T[IC]
        if temp_f <= 0.0:
            # ISA standard day + optional hot/cold offset (DT_ISA, °F = °R delta)
            alt_ft = com_zinput.ALT[IC]
            if alt_ft <= 36000.0:
                T_RANKINE = T0_ISA - LAPSE_RATE * alt_ft + com_zinput.DT_ISA[IC]
            else:
                T_RANKINE = T_TROPO + com_zinput.DT_ISA[IC]
        else:
            T_RANKINE = temp_f + 459.69   # convert user-specified °F to Rankine

        TO = T0_RANKINE
        TOT = TO / T_RANKINE
        FC[IC] = np.sqrt(TOT)          # temperature correction factor
        
        # Pressure ratio from standard atmosphere table
        # FIX 3: unint() returns (Y, L) – must unpack the tuple
        POP, LIMIT = unint(11, ALTPR, PRESSR, com_zinput.ALT[IC])
        
        # Density ratio ρ0/ρ  – FIX 2: use module-level RORO[], not com_zinput.RORO[]
        RORO[IC] = 1.0 / (POP * TOT)
        
        # ===================================================================
        # End of density ratio block
        # ===================================================================
        
        # The AF, C_Li, Blades, Diameter and Tip-speed loops will be added
        # in the next blocks (Block 5 and following).
        
        # For now we just process one operating condition at a time.
        _emit(f"Processing operating condition {IC+1} (IW={IW}) - "
              f"Altitude={com_zinput.ALT[IC]:.0f} ft, "
              f"Density ratio={RORO[IC]:.6f}")

        # ===================================================================
        # BLOCK 5: AF loop (DO 1200 IAF=1,NAF) + header printing
        # ===================================================================
   
        # AFT = AF - DAF   (initialize before the loop)
        AFT = com_zinput.AF - com_zinput.DAF
        
        # Special header for reverse thrust (IW == 3)
        if IW == 3:
            _emit("\n" + " " * 21 + "REVERSE THRUST COMPUTATION")
            if com_zinput.ROT == 1.0:
                _emit(" " * 24 + "RECIPROCATING ENGINE")
            else:
                _emit(" " * 27 + "TURBINE ENGINE")
            _emit(" " * 22 + f"FULL THROTTLE SHP   = {com_zinput.BHP[IC]:6.0f}")
            _emit(" " * 22 + f"FULL THROTTLE RPM = {com_zinput.RPMC[IC]:6.0f}")
            _emit(" " * 22 + f"TOUCH DOWN V-KNOTS = {com_zinput.ANDVK[IC]:6.0f}")
            _emit(" " * 22 + f"ALTITUDE FEET     = {com_zinput.ALT[IC]:6.0f}")
            _emit(" " * 22 + f"TEMPERATURE RANKINE= {T_RANKINE:6.0f}\n")
            # FIX 5: Fortran falls through from label 2000 → label 270 (AF loop).
            # Do NOT return here – the AF loop below runs for IW==3 as well.

        else:
            # Normal forward-flight header (only for IW != 3)
            _emit("\n" + " " * 18 + "OPERATING CONDITION\n")

            # Cost/weight header (if requested)
            if NCOST == 1:
                # IENT=1 → initialize cost/weight factors (use dummy BLADT for initialization)
                CCLF1, CCLF, _, _, _, _, _ = cost(
                    com_zinput.WTCON, com_zinput.BLADN, com_zinput.CLF1, com_zinput.CLF,
                    com_zinput.CK70, com_zinput.CK80, com_zinput.CAMT,
                    com_zinput.DAMT, com_zinput.NAMT, com_zinput.CQUAN,
                    0.0, 0.0,  # WT70, WT80 (not used for IENT=1)
                    com_zinput.COST70, com_zinput.COST80,
                    0.0, 0.0, 0.0, 0.0,  # CCLF1, CCLF, CCK70, CCK80 (will be set)
                    1)  # IENT=1 for initialization
                if IW == 1:
                    _emit(f" SHP   = {com_zinput.BHP[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}   "
                          f"UNIT FACTOR L.C.   = {com_zinput.CLF1:5.2f}")
                else:
                    _emit(f" THRUST = {com_zinput.THRUST[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}   "
                          f"UNIT FACTOR L.C.   = {com_zinput.CLF1:5.2f}")
            else:
                CCLF1 = 0.0
                CCLF = 0.0
                # Normal header without cost
                if IW == 1:
                    _emit(f" SHP   = {com_zinput.BHP[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}")
                else:
                    _emit(f" THRUST = {com_zinput.THRUST[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}")

            _emit(f" ALT-FT = {com_zinput.ALT[IC]:7.0f}   "
                  f"DESIGN FLIGHT M.={com_zinput.ZMWT:5.3f}")
            _emit(f" V-KTAS = {com_zinput.VKTAS[IC]:7.1f}   "
                  f"CLASSIFICATION = {com_zinput.WTCON:5.0f}")
            _emit(f" TEMP R = {T_RANKINE:7.0f}   "
                  f"FIELD POINT FT = {com_zinput.DIST[IC]:5.0f}\n")
        
        # ======================  AF LOOP STARTS HERE  ======================
        for IAF in range(int(com_zinput.NAF)):
            AFT = AFT + com_zinput.DAF
            
            # Range check (AF must be between 80 and 200)
            if not (80.0 <= AFT <= 200.0):
                _emit(f" ILLEGAL ACTIVITY FACTOR = {AFT:8.1f}")
                continue
            
            # The inner loops (C_Li, Blades, Diameter, Tip-speed) will be added
            # in the following blocks.
            # For now we just print the current AF value for visibility.
            _emit(f" → Current Activity Factor = {AFT:6.1f}")
            
            # ====================== C_Li LOOP (Block 6) ======================
            NCLI = int(com_zinput.ZNCLI + 0.1)      # equivalent to ZNCLI + .1
            CLI = com_zinput.CLII - com_zinput.DCLI
            
            for ICL in range(NCLI):
                CLI += com_zinput.DCLI
                
                # Range check for C_Li (0.3 to 0.8)
                if not (0.29999 <= CLI <= 0.80001):
                    _emit(f" ILLEGAL INTEGRATED DESIGN CL = {CLI:5.3f}")
                    continue
                
                # CLI is valid - continue to next nested loops (Blades, Diameter, Tip-speed)
                _emit(f"   → Current C_Li = {CLI:5.3f}")
                
                            # ====================== BLADES LOOP (Block 7) ======================
                BLADT = com_zinput.BLADN - com_zinput.DBLAD
            
                for IB in range(int(com_zinput.NBL)):
                    BLADT += com_zinput.DBLAD
                    
                    # Range check for number of blades (2 to 8)
                    if not (2.0 <= BLADT <= 8.0):
                        _emit(f" ILLEGAL NO. OF BLADES = {BLADT:8.1f}")
                        continue
                    
                    _emit(f"     → Current Blades = {BLADT:3.0f}")
                    
                    # Next block (Diameter loop) will be inserted here
                    # (Block 8)
                                    # ====================== DIAMETER LOOP (Block 8) ======================
                    DIA = com_zinput.D - com_zinput.DD
                    
                    for ID in range(int(com_zinput.ND)):
                        DIA += com_zinput.DD

                        # Range check is not needed for diameter (no hard limit in original code)
                        _emit(f"       → Current Diameter = {DIA:6.2f} ft")

                        # ── Fortran: IF (IW.EQ.3) GO TO 3000 ────────────────────────────────
                        # For reverse thrust (IW=3) bypass the tip-speed loop entirely and
                        # call REVTHT once per power-setting step (Fortran labels 3000–3900).
                        if IW == 3:
                            CP = 0.0
                            IRT   = com_zinput.NPCPW[IC]
                            PCPWC = com_zinput.PCPW[IC]
                            for _ in range(IRT):
                                if com_zinput.RTC == 1.0:
                                    # Compute CP from BHP / RPM (Fortran label 3100)
                                    CP = (com_zinput.BHP[IC] * PCPWC * RORO[IC] * 1e11
                                          / (2.0 * com_zinput.RPMC[IC]**3 * DIA**5 * 100.0))
                                revtht(com_zinput.RTC, com_zinput.ROT,
                                       AFT, CLI, BLADT, DIA,
                                       CP, com_zinput.BETA[IC], RORO[IC],
                                       com_zinput.BHP[IC], com_zinput.RPMC[IC],
                                       PCPWC, com_zinput.ANDVK[IC],
                                       IC=IC + 1, collector=_collector)
                                PCPWC += com_zinput.DPCPW[IC]
                            continue   # next diameter (Fortran falls through to label 800)

                        # ====================== TIP-SPEED / STALL LOOP (Block 9) ======================
                        # NTS is set earlier in the operating condition block
                        NTS = int(com_zinput.NDTS[IC]) if com_zinput.STALIT[IC] <= 0.50 else 10

                        # Initialize tip speed and stall work arrays
                        # Fortran: TRIG=0, TIPSDG(1)=700, DTS=0 for stall mode (lines 148-152)
                        TRIG = 0.0
                        IFIN = 0
                        if com_zinput.STALIT[IC] > 0.50:
                            com_zinput.DTS[IC] = 0.0   # Fortran sets DTS=0 for stall mode
                            TIPSDG[0] = 700.0
                            TIPSPD    = 700.0
                            BHPG[:]   = 0.0
                            THRSTG[:] = 0.0
                        else:
                            TIPSPD = com_zinput.TS[IC] - com_zinput.DTS[IC]

                        for ITS in range(NTS):
                            TIPSPD += com_zinput.DTS[IC]   # adds 0 for stall mode

                            # MACH NUMBER AND ADVANCE RATIO J CALCULATION
                            ZMS[0] = MACH_KTAS_FACTOR * com_zinput.VKTAS[IC] * FC[IC]
                            ZMS[1] = TIPSPD * FC[IC] / SPEED_OF_SOUND
                            ZM1 = ZMS[0]

                            ZJI = J_CONV * com_zinput.VKTAS[IC] / TIPSPD

                            if ZJI == 0.0:
                                ZM1 = ZMS[1]

                            # Advance ratio limit check
                            if (com_zinput.STALIT[IC] <= 0.50 and ZJI > 5.0) or \
                               (com_zinput.STALIT[IC] > 0.50 and ZJI > 3.0):
                                _emit(f" ADVANCE RATIO TOO HIGH = {ZJI:8.4f}")
                                continue

                            # ====================== 50% STALL ITERATION ======================
                            # Fortran labels 169-201: log-linear secant on TIPSPD until
                            # BHP (or THRUST) from perfm(IW=3) matches the operating value
                            # within 0.5%.  Two initial guesses: 700 fps then 400 fps.
                            stall_converged = False
                            if com_zinput.STALIT[IC] > 0.50:
                                TIPSDG[ITS] = TIPSPD    # record tip speed at this iteration
                                IWSV = IW
                                IW = 3
                                # Pre-compute CP from BHP (IW=1) or 0 (IW=2) at current tip speed.
                                # For IW=1: PERFM fall-through uses this CP for CTANG-based CT.
                                # For IW=2: CT comes from CTSTAL (pass CP=0 to keep pure stall path).
                                if IWSV == 1:
                                    CP_pre = (com_zinput.BHP[IC] * 1e11 * RORO[IC]
                                              / (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR))
                                else:
                                    CP_pre = 0.0
                                _afc, _cpe, _ast = state.as_afcor(), state.as_cpecte(), state.as_astrk()
                                perfm(3, CP_pre, ZJI, AFT, BLADT, CLI, 0.0, ZMS, 0,
                                      _afc, _cpe, _ast)
                                state.sync_from_perfm(_afc, _cpe, _ast)
                                CP_stall = state.CPE
                                CT_stall = state.CTE
                                BLLLL    = state.BLLLL
                                IW = IWSV   # restore original IW

                                if IW == 1:   # Fortran label 711
                                    BHPG[ITS] = (2.0 * TIPSDG[ITS]**3 * DIA**2 *
                                                 RPM_FACTOR * CP_stall / (1e11 * RORO[IC]))
                                    if abs(com_zinput.BHP[IC] - BHPG[ITS]) < 0.005 * com_zinput.BHP[IC]:
                                        CP = CP_stall; CT = CT_stall; XFT = 1.0
                                        THRUST_IC = (CT * TIPSPD**2 * DIA**2 *
                                                     THRUST_CONV / (THRUST_DENOM * RORO[IC]))
                                        TRIG = 1.0; stall_converged = True
                                    elif ITS == 0:
                                        TIPSDG[1] = 400.0; TIPSPD = TIPSDG[1]
                                    else:
                                        TIPSDG[ITS+1] = (
                                            (np.log(com_zinput.BHP[IC]) - np.log(BHPG[ITS-1])) *
                                            (TIPSDG[ITS] - TIPSDG[ITS-1]) /
                                            (np.log(BHPG[ITS]) - np.log(BHPG[ITS-1]))
                                            + TIPSDG[ITS-1])
                                        TIPSPD = TIPSDG[ITS+1]

                                else:   # IW == 2, Fortran label 712
                                    THRSTG[ITS] = (TIPSDG[ITS]**2 * DIA**2 *
                                                   THRUST_CONV * CT_stall / (THRUST_DENOM * RORO[IC]))
                                    if abs(com_zinput.THRUST[IC] - THRSTG[ITS]) < 0.005 * com_zinput.THRUST[IC]:
                                        TIPSPD = TIPSDG[ITS]
                                        CP = CP_stall; CT = CT_stall; XFT = 1.0
                                        BHP_IC = (CP * 2.0 * TIPSPD**3 * DIA**2 *
                                                  RPM_FACTOR / (1e11 * RORO[IC]))
                                        TRIG = 1.0; stall_converged = True
                                    elif ITS == 0:
                                        TIPSDG[1] = 400.0; TIPSPD = TIPSDG[1]
                                    else:
                                        TIPSDG[ITS+1] = (
                                            (np.log(com_zinput.THRUST[IC]) - np.log(THRSTG[ITS-1])) *
                                            (TIPSDG[ITS] - TIPSDG[ITS-1]) /
                                            (np.log(THRSTG[ITS]) - np.log(THRSTG[ITS-1]))
                                            + TIPSDG[ITS-1])
                                        TIPSPD = TIPSDG[ITS+1]

                                if not stall_converged:
                                    if ITS == NTS - 1:
                                        _emit(" FAILED STALL ITERATION")
                                    continue   # next ITS; fall through only when converged

                            # ====================== NORMAL PERFORMANCE CALCULATION ======================
                            # Skipped when stall converged (CP/CT/THRUST_IC or BHP_IC already set above)
                            IFIN = 0
                            if not stall_converged:
                                _afc, _cpe, _ast = state.as_afcor(), state.as_cpecte(), state.as_astrk()

                                if IW == 1:
                                    CP = com_zinput.BHP[IC] * 1e11 * RORO[IC] / \
                                         (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR)
                                    IFIN = perfm(1, CP, ZJI, AFT, BLADT, CLI, 0.0, ZMS, 0,
                                                 _afc, _cpe, _ast)
                                    state.sync_from_perfm(_afc, _cpe, _ast)
                                    CP    = state.CPE
                                    CT    = state.CTE
                                    XFT   = state.XFT
                                    BLLLL = state.BLLLL
                                    THRUST_IC = (9999999999. if CT == state.ASTERK else
                                                 CT * TIPSPD**2 * DIA**2 /
                                                 (THRUST_DENOM * RORO[IC]) * THRUST_CONV * XFT)

                                elif IW == 2:
                                    CT = com_zinput.THRUST[IC] * THRUST_DENOM * RORO[IC] / \
                                         (TIPSPD**2 * DIA**2 * THRUST_CONV)
                                    IFIN = perfm(2, 0.0, ZJI, AFT, BLADT, CLI, CT, ZMS, 0,
                                                 _afc, _cpe, _ast)
                                    state.sync_from_perfm(_afc, _cpe, _ast)
                                    CP    = state.CPE
                                    CT    = state.CTE
                                    XFT   = state.XFT
                                    BLLLL = state.BLLLL
                                    BHP_IC = (9999999999. if CP == state.ASTERK else
                                              CP * 2.0 * TIPSPD**3 * DIA**2 /
                                              (1e11 * RORO[IC]) * RPM_FACTOR)

                            # ====================== NOISE CALCULATION ======================
                            PNL = 0.0
                            if com_zinput.DIST[IC] > 0.0:
                                BHP_for_noise = com_zinput.BHP[IC] if IW == 1 else BHP_IC
                                PNL, _ = znoise(BLADT, DIA, TIPSPD, com_zinput.VKTAS[IC],
                                                BHP_for_noise, com_zinput.DIST[IC],
                                                FC[IC], com_zinput.XNOE)

                            # ====================== WEIGHT AND COST CALCULATION ======================
                            WT70 = 0.0
                            WT80 = 0.0
                            COST70_result = 0.0
                            COST80_result = 0.0
                            QTY70_list = []
                            QTY80_list = []
                            COST70_list = []
                            COST80_list = []
                            if NCOST == 1:
                                # Calculate weight for 1970 and 1980 technology
                                BHP_for_weight = com_zinput.BHP[IC] if IW == 1 else BHP_IC
                                WT70, WT80 = wait(com_zinput.WTCON, com_zinput.ZMWT, BHP_for_weight,
                                                   DIA, AFT, BLADT, TIPSPD)

                                # IENT=2 → compute costs
                                _, _, _, _, CQUAN_result, COST70, COST80 = cost(
                                    com_zinput.WTCON, BLADT, com_zinput.CLF1, com_zinput.CLF,
                                    com_zinput.CK70, com_zinput.CK80, com_zinput.CAMT,
                                    com_zinput.DAMT, com_zinput.NAMT, com_zinput.CQUAN,
                                    WT70, WT80,
                                    com_zinput.COST70, com_zinput.COST80,
                                    CCLF1, CCLF, 0.0, 0.0,  # CCK70, CCK80 (computed in cost())
                                    2)  # IENT=2 for computation

                                # Extract quantity and cost arrays
                                if com_zinput.NAMT > 0:
                                    COST70_result = COST70[0]
                                    COST80_result = COST80[0]
                                    # Store arrays for all quantity levels
                                    for i in range(com_zinput.NAMT):
                                        QTY70_list.append(CQUAN_result[0, i])
                                        QTY80_list.append(CQUAN_result[1, i])
                                        COST70_list.append(COST70[i])
                                        COST80_list.append(COST80[i])

                            # ── Emit result (print + structured collector) ──────────
                            THRUST_out = THRUST_IC if IW == 1 else com_zinput.THRUST[IC]
                            SHP_out    = com_zinput.BHP[IC] if IW == 1 else BHP_IC
                            eta        = (ZJI * CT / CP) if CP != 0.0 else 0.0
                            eff_str    = f"{eta*100:5.2f}%" if eta > 0.0 else "  — "
                            # Propeller RPM and shaft torque
                            RPM_prop      = TIPSPD * 60.0 / (np.pi * DIA)
                            torque_ftlbf  = (SHP_out * 5252.11 / RPM_prop) if RPM_prop > 0.0 else 0.0

                            # Convert dimensional values for log display
                            _si = (_unit_system == "SI")
                            log_dia    = DIA           * FT_TO_M     if _si else DIA
                            log_vt     = TIPSPD        * FPS_TO_MS   if _si else TIPSPD
                            log_thr    = THRUST_out    * LBF_TO_N    if _si else THRUST_out
                            log_shp    = SHP_out       * HP_TO_KW    if _si else SHP_out
                            log_torque = torque_ftlbf  * FTLBF_TO_NM if _si else torque_ftlbf
                            d_u  = "m"     if _si else "ft"
                            vt_u = "m/s"   if _si else "fps"
                            t_u  = "N"     if _si else "lbf"
                            p_u  = "kW"    if _si else "hp"
                            q_u  = "N·m"   if _si else "ft·lbf"

                            result_line = (
                                f"         Diameter={log_dia:6.2f}{d_u}  TipSpd={log_vt:7.1f}{vt_u}  "
                                f"CP={CP:8.4f}  CT={CT:8.4f}  Eff={eff_str}  "
                                f"BLLLL={BLLLL:6.2f}  "
                                f"Thrust={log_thr:9.0f}{t_u}  SHP={log_shp:8.0f}{p_u}"
                                f"  Torque={log_torque:8.1f}{q_u}  PNL={PNL:6.1f}"
                            )

                            # Append weight/cost on the same line — one line per iteration
                            if NCOST == 1:
                                wt_u = "kg" if _si else "lb"
                                log_wt70 = WT70 * LB_TO_KG if _si else WT70
                                log_wt80 = WT80 * LB_TO_KG if _si else WT80
                                if QTY70_list:
                                    n = max(len(QTY70_list), len(QTY80_list))
                                    for i in range(n):
                                        q70 = QTY70_list[i]  if i < len(QTY70_list)  else 0.0
                                        c70 = COST70_list[i] if i < len(COST70_list) else 0.0
                                        q80 = QTY80_list[i]  if i < len(QTY80_list)  else 0.0
                                        c80 = COST80_list[i] if i < len(COST80_list) else 0.0
                                        if i == 0:
                                            result_line += (
                                                f"  Qty70={q70:8.0f}  Wt70={log_wt70:7.1f}{wt_u}"
                                                f"  Cost70=${c70:9.2f}"
                                                f"  Qty80={q80:8.0f}  Wt80={log_wt80:7.1f}{wt_u}"
                                                f"  Cost80=${c80:9.2f}"
                                            )
                                        else:
                                            result_line += (
                                                f"  Qty70={q70:8.0f}  Cost70=${c70:9.2f}"
                                                f"  Qty80={q80:8.0f}  Cost80=${c80:9.2f}"
                                            )
                                else:
                                    result_line += (
                                        f"  Wt70={log_wt70:7.1f}{wt_u}  Wt80={log_wt80:7.1f}{wt_u}"
                                    )

                            _emit(result_line)

                            # Feed structured row to HMI collector if attached
                            if _collector is not None:
                                from output import ResultRow
                                _collector.add_row(ResultRow(
                                    condition  = IC + 1,
                                    blades     = BLADT,
                                    af         = AFT,
                                    cli        = CLI,
                                    dia_ft     = DIA,
                                    tipspd_fps = TIPSPD,
                                    cp         = CP,
                                    ct         = CT,
                                    blade_ang  = BLLLL,
                                    j          = ZJI,
                                    mach_tip   = ZMS[1],
                                    mach_fs    = ZMS[0],
                                    ft         = XFT,
                                    eta        = eta,
                                    thrust_lb  = THRUST_out,
                                    shp        = SHP_out,
                                    torque     = torque_ftlbf,
                                    pnl_db     = PNL,
                                    wt70_lb    = WT70,
                                    wt80_lb    = WT80,
                                    cost70     = COST70_result,
                                    cost80     = COST80_result,
                                    qty70      = QTY70_list,
                                    qty80      = QTY80_list,
                                    cost70_qty = COST70_list,
                                    cost80_qty = COST80_list,
                                    off_chart  = (CP >= state.ASTERK or CT >= state.ASTERK),
                                ))

                            # FIX 7: loop-exit flags (Fortran label 40 checks)
                            if TRIG == 1.0:      # stall converged → exit tip-speed loop
                                break
                            if IFIN == 7710:     # PERFM returned off-chart → exit diameter loop
                                break
                        # end ITS loop

                        # FIX 7: IFIN/ISTALL propagate the break to the diameter loop
                        if IFIN == 7710:
                            continue             # skip remaining tip-speeds, next diameter
                        ISTALL = 0              # FIX 7: stall flag (set to 2 by stall logic when converged)

# ===================================================================
# PROPELLER CHARACTERISTIC MAP
# ===================================================================

def run_map(conditions: List[OperatingCondition],
            geometry:   PropellerGeometry,
            ic_index:   int   = 0,
            j_start:    float = 0.0,
            j_end:      float = 1.4,
            nj:         int   = 30):
    """
    Generate a propeller characteristic map (CP, CT, η vs J).

    For each (AF, CLi, blades, diameter, tip-speed) combination in the
    geometry sweep, PERFM is called at nj evenly-spaced J values.
    CP is held fixed (derived from BHP[ic_index], Vt, D, RORO) — the
    resulting CT(J) and η(J) = J·CT/CP curves are the map.

    IW=3 (reverse thrust) conditions are not supported and raise ValueError.
    Returns a MapResult (importable from output.py).
    """
    from output import MapPoint, MapCurve, MapResult

    load_conditions(conditions, geometry, state)

    IC = ic_index
    IW = state.IWIC[IC]
    if IW == 3:
        raise ValueError("Propeller map is not available for IW=3 (reverse thrust).")

    # ── Atmosphere for selected condition (mirrors main_loop) ─────────
    temp_f = state.T[IC]
    if temp_f <= 0.0:
        alt_ft = state.ALT[IC]
        if alt_ft <= TROPO_ALT:
            T_RANKINE = T0_ISA - LAPSE_RATE * alt_ft + state.DT_ISA[IC]
        else:
            T_RANKINE = T_TROPO + state.DT_ISA[IC]
    else:
        T_RANKINE = temp_f + 459.69

    TOT    = T0_RANKINE / T_RANKINE
    FC_ic  = float(np.sqrt(TOT))
    POP, _ = unint(11, ALTPR, PRESSR, state.ALT[IC])
    RORO_ic = 1.0 / (POP * TOT)

    # ── J axis ────────────────────────────────────────────────────────
    j_step   = (j_end - j_start) / max(nj - 1, 1)
    j_values = [j_start + i * j_step for i in range(nj)]

    result = MapResult()

    # ── Geometry sweep (mirrors the nested loops in main_loop) ────────
    AFT = state.AF - state.DAF
    for _ in range(int(state.NAF)):
        AFT += state.DAF
        if not (80.0 <= AFT <= 200.0):
            continue

        CLI = state.CLII - state.DCLI
        for _ in range(int(state.ZNCLI)):
            CLI += state.DCLI
            if not (0.29999 <= CLI <= 0.80001):
                continue

            BLADT = state.BLADN - state.DBLAD
            for _ in range(int(state.NBL)):
                BLADT += state.DBLAD
                if not (2.0 <= BLADT <= 8.0):
                    continue

                DIA = state.D - state.DD
                for _ in range(int(state.ND)):
                    DIA += state.DD

                    TIPSPD = state.TS[IC] - state.DTS[IC]
                    for _ in range(int(state.NDTS[IC])):
                        TIPSPD += state.DTS[IC]

                        # Fixed CP for this (BHP/THRUST, Vt, D, RORO)
                        if IW == 1:
                            CP_input = (state.BHP[IC] * 1e11 * RORO_ic /
                                        (2.0 * TIPSPD**3 * DIA**2 * RPM_FACTOR))
                        else:  # IW == 2
                            # CT is fixed; CP starts as zero (PERFM IW=2 path)
                            CT_input = (state.THRUST[IC] * THRUST_DENOM * RORO_ic /
                                        (TIPSPD**2 * DIA**2 * THRUST_CONV))
                            CP_input = 0.0

                        # ── J sweep ──────────────────────────────────
                        points = []
                        for J in j_values:
                            if J > 5.0:
                                break  # beyond PERFM table range

                            # Mach numbers at this J/airspeed
                            V_ktas = J * TIPSPD / J_CONV
                            ZMS_map = np.zeros(2)
                            ZMS_map[1] = TIPSPD * FC_ic / SPEED_OF_SOUND
                            ZMS_map[0] = (ZMS_map[1] if J == 0.0
                                          else MACH_KTAS_FACTOR * V_ktas * FC_ic)

                            _afc = state.as_afcor()
                            _cpe = state.as_cpecte()
                            _ast = state.as_astrk()

                            if IW == 1:
                                perfm(1, CP_input, J, AFT, BLADT, CLI, 0.0,
                                      ZMS_map, 0, _afc, _cpe, _ast)
                            else:
                                perfm(2, 0.0, J, AFT, BLADT, CLI, CT_input,
                                      ZMS_map, 0, _afc, _cpe, _ast)
                            state.sync_from_perfm(_afc, _cpe, _ast)

                            off = (state.CPE >= state.ASTERK or
                                   state.CTE >= state.ASTERK)
                            if off:
                                points.append(MapPoint(j=J, off_chart=True))
                            else:
                                CP_out = state.CPE
                                CT_out = state.CTE
                                eta    = (J * CT_out / CP_out
                                          if CP_out > 0.0 and J > 0.0 else 0.0)
                                points.append(MapPoint(
                                    j=J, cp=CP_out, ct=CT_out, eta=eta,
                                    blade_ang=state.BLLLL))

                        label = (f"{BLADT:.0f}bl  AF={AFT:.0f}"
                                 f"  CLi={CLI:.2f}"
                                 f"  D={DIA:.1f}ft  Vt={TIPSPD:.0f}fps")
                        result.curves.append(MapCurve(
                            label=label, blades=BLADT, af=AFT, cli=CLI,
                            dia_ft=DIA, vt_fps=TIPSPD, points=points))

    return result


# ===================================================================
# Run the program
# ===================================================================
if __name__ == "__main__":
    main_loop()