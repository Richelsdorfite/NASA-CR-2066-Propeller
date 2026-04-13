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
# Set this to a ResultsCollector instance before calling main_loop() to
# receive structured ResultRow objects directly (used by HMI.py).
# Leave as None for command-line / plain-text use.
_collector = None   # type: ignore
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
    print("\n" + "="*80)
    print(" " * 19 + "HAMILTON STANDARD COMPUTER DECK NO. H432")
    print(" " * 17 + "COMPUTES PERFORMANCE, NOISE, WEIGHT, AND COST FOR")
    print(" " * 26 + "GENERAL AVIATION PROPELLERS")
    print("="*80 + "\n")


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
            print(f"INPUT ERROR, IW= {IW} IC= {IC+1}")
            continue
        
        # ===================================================================
        # DENSITY RATIO CALCULATION (lines ~100–180)
        # ===================================================================
        
        # Temperature handling
        temp_f = com_zinput.T[IC]
        if temp_f <= 0.0:
            alt_ft = com_zinput.ALT[IC]
            if alt_ft <= 36000.0:
                temp_f = T0_ISA - LAPSE_RATE * alt_ft
            else:
                temp_f = T_TROPO
        else:
            temp_f = temp_f + 459.69   # convert °F to Rankine
        
        com_zinput.T[IC] = temp_f
        
        TO = T0_RANKINE
        TOT = TO / temp_f
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
        print(f"Processing operating condition {IC+1} (IW={IW}) - "
              f"Altitude={com_zinput.ALT[IC]:.0f} ft, "
              f"Density ratio={RORO[IC]:.6f}")

        # ===================================================================
        # BLOCK 5: AF loop (DO 1200 IAF=1,NAF) + header printing
        # ===================================================================
   
        # AFT = AF - DAF   (initialize before the loop)
        AFT = com_zinput.AF - com_zinput.DAF
        
        # Special header for reverse thrust (IW == 3)
        if IW == 3:
            print("\n" + " " * 21 + "REVERSE THRUST COMPUTATION")
            if com_zinput.ROT == 1.0:
                print(" " * 27 + "TURBINE ENGINE")
            else:
                # FIX 4: indented correctly under else
                print(" " * 24 + "RECIPROCATING ENGINE")
            print(f" " * 22 + f"FULL THROTTLE SHP   = {com_zinput.BHP[IC]:6.0f}")
            print(f" " * 22 + f"FULL THROTTLE RPM = {com_zinput.RPMC[IC]:6.0f}")
            print(f" " * 22 + f"TOUCH DOWN V-KNOTS = {com_zinput.ANDVK[IC]:6.0f}")
            print(f" " * 22 + f"ALTITUDE FEET     = {com_zinput.ALT[IC]:6.0f}")
            print(f" " * 22 + f"TEMPERATURE RANKINE= {com_zinput.T[IC]:6.0f}\n")
            # FIX 5: Fortran falls through from label 2000 → label 270 (AF loop).
            # Do NOT return here – the AF loop below runs for IW==3 as well.

        else:
            # Normal forward-flight header (only for IW != 3)
            print("\n" + " " * 18 + "OPERATING CONDITION\n")

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
                    print(f" SHP   = {com_zinput.BHP[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}   "
                          f"UNIT FACTOR L.C.   = {com_zinput.CLF1:5.2f}")
                else:
                    print(f" THRUST = {com_zinput.THRUST[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}   "
                          f"UNIT FACTOR L.C.   = {com_zinput.CLF1:5.2f}")
            else:
                CCLF1 = 0.0
                CCLF = 0.0
                # Normal header without cost
                if IW == 1:
                    print(f" SHP   = {com_zinput.BHP[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}")
                else:
                    print(f" THRUST = {com_zinput.THRUST[IC]:7.0f}   "
                          f"NO. OF ENGINES = {com_zinput.XNOE:5.0f}")

            print(f" ALT-FT = {com_zinput.ALT[IC]:7.0f}   "
                  f"DESIGN FLIGHT M.={com_zinput.ZMWT:5.3f}")
            print(f" V-KTAS = {com_zinput.VKTAS[IC]:7.1f}   "
                  f"CLASSIFICATION = {com_zinput.WTCON:5.0f}")
            print(f" TEMP R = {com_zinput.T[IC]:7.0f}   "
                  f"FIELD POINT FT = {com_zinput.DIST[IC]:5.0f}\n")
        
        # ======================  AF LOOP STARTS HERE  ======================
        for IAF in range(int(com_zinput.NAF)):
            AFT = AFT + com_zinput.DAF
            
            # Range check (AF must be between 80 and 200)
            if not (80.0 <= AFT <= 200.0):
                print(f" ILLEGAL ACTIVITY FACTOR = {AFT:8.1f}")
                continue
            
            # The inner loops (C_Li, Blades, Diameter, Tip-speed) will be added
            # in the following blocks.
            # For now we just print the current AF value for visibility.
            print(f" → Current Activity Factor = {AFT:6.1f}")
            
            # ====================== C_Li LOOP (Block 6) ======================
            NCLI = int(com_zinput.ZNCLI + 0.1)      # equivalent to ZNCLI + .1
            CLI = com_zinput.CLII - com_zinput.DCLI
            
            for ICL in range(NCLI):
                CLI += com_zinput.DCLI
                
                # Range check for C_Li (0.3 to 0.8)
                if not (0.29999 <= CLI <= 0.80001):
                    print(f" ILLEGAL INTEGRATED DESIGN CL = {CLI:5.3f}")
                    continue
                
                # CLI is valid - continue to next nested loops (Blades, Diameter, Tip-speed)
                print(f"   → Current C_Li = {CLI:5.3f}")
                
                            # ====================== BLADES LOOP (Block 7) ======================
                BLADT = com_zinput.BLADN - com_zinput.DBLAD
            
                for IB in range(int(com_zinput.NBL)):
                    BLADT += com_zinput.DBLAD
                    
                    # Range check for number of blades (2 to 8)
                    if not (2.0 <= BLADT <= 8.0):
                        print(f" ILLEGAL NO. OF BLADES = {BLADT:8.1f}")
                        continue
                    
                    print(f"     → Current Blades = {BLADT:3.0f}")
                    
                    # Next block (Diameter loop) will be inserted here
                    # (Block 8)
                                    # ====================== DIAMETER LOOP (Block 8) ======================
                    DIA = com_zinput.D - com_zinput.DD
                    
                    for ID in range(int(com_zinput.ND)):
                        DIA += com_zinput.DD
                        
                        # Range check is not needed for diameter (no hard limit in original code)
                        print(f"       → Current Diameter = {DIA:6.2f} ft")
                        
                        # The innermost Tip-speed / stall loop (Block 9) will be inserted here
                                    # ====================== TIP-SPEED / STALL LOOP (Block 9) ======================
                        # NTS is set earlier in the operating condition block
                        NTS = int(com_zinput.NDTS[IC]) if com_zinput.STALIT[IC] <= 0.50 else 10

                        # Initialize tip speed
                        # FIX 6: TIPSDG[0] must be set to 700 for the stall iteration
                        #         (Fortran line 150: TIPSDG(1)=700.)
                        TRIG = 0.0    # FIX 7: flag – set to 1 when stall converges (→ exits tip-speed loop)
                        if com_zinput.STALIT[IC] > 0.50:
                            TIPSDG[0] = 700.0       # FIX 6: first stall-guess tip-speed
                            TIPSPD    = 700.0
                        else:
                            TIPSPD = com_zinput.TS[IC] - com_zinput.DTS[IC]

                        for ITS in range(NTS):
                            TIPSPD += com_zinput.DTS[IC]
                            
                            # MACH NUMBER AND ADVANCE RATIO J CALCULATION
                            ZMS[0] = MACH_KTAS_FACTOR * com_zinput.VKTAS[IC] * FC[IC]      # freestream Mach
                            ZMS[1] = TIPSPD * FC[IC] / SPEED_OF_SOUND                       # tip Mach
                            ZM1 = ZMS[0]
                            
                            ZJI = J_CONV * com_zinput.VKTAS[IC] / TIPSPD
                            
                            if ZJI == 0.0:
                                ZM1 = ZMS[1]
                            
                            # Advance ratio limit check
                            if (com_zinput.STALIT[IC] <= 0.50 and ZJI > 5.0) or \
                               (com_zinput.STALIT[IC] > 0.50 and ZJI > 3.0):
                                print(f" ADVANCE RATIO TOO HIGH = {ZJI:8.4f}")
                                continue
                            
                            # ====================== 50% STALL ITERATION (when requested) ======================
                            if com_zinput.STALIT[IC] > 0.50:
                                IWSV = IW
                                IW = 3
                                _afc, _cpe, _ast = state.as_afcor(), state.as_cpecte(), state.as_astrk()
                                perfm(3, 0.0, ZJI, AFT, BLADT, CLI, 0.0, ZMS, 0,
                                      _afc, _cpe, _ast)
                                state.sync_from_perfm(_afc, _cpe, _ast)
                                IW = IWSV
                                print(f"   → Stall iteration at tip speed = {TIPSPD:7.1f} fps")
                                continue

                            # ====================== NORMAL PERFORMANCE CALCULATION ======================
                            IFIN = 0
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
                            print(f"         Diameter={DIA:6.2f}  TipSpd={TIPSPD:7.1f}  "
                                  f"CP={CP:8.4f}  CT={CT:8.4f}  BLLLL={BLLLL:6.2f}  "
                                  f"Thrust={THRUST_out:9.0f}  SHP={SHP_out:8.0f}  PNL={PNL:6.1f}")

                            # Print weight/cost breakdown if computed (grouped by technology, one line)
                            if NCOST == 1:
                                cost_line = f"           Wt70={WT70:6.1f}lb  Wt80={WT80:6.1f}lb"
                                if QTY70_list:
                                    # Add quantities and costs (first 4 levels)
                                    for i in range(min(4, len(QTY70_list))):
                                        cost_line += f"  |Qty70:{QTY70_list[i]:7.0f}/${COST70_list[i]:6.2f}"
                                    for i in range(min(4, len(QTY80_list))):
                                        cost_line += f"  |Qty80:{QTY80_list[i]:7.0f}/${COST80_list[i]:6.2f}"
                                print(cost_line)

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
                                    thrust_lb  = THRUST_out,
                                    shp        = SHP_out,
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
# Run the program
# ===================================================================
if __name__ == "__main__":
    main_loop()