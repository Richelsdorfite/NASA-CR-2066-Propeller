# IW=1 vs IW=2 Compressibility Asymmetry

## The Asymmetry

### IW=1 (Power-specified) - Compressibility Applied AFTER
```
K loop:
  CP (given) → unint() → BldAng → CPP
  [NO XFFT involved in blade angle lookup]

After K loop (label 310):
  CTE = CTT × AFCT × TCLI
  Separate XFFT correction applied
  Result: Blade angle independent of XFFT
```

### IW=2 (Thrust-specified) - Compressibility Baked INSIDE
```
K loop:
  CT (given) → secant iteration WITH XFFT entangled → CTA/XFFT → CTN
  CTE = CTN × AFCT × TCLI
  [XFFT used DURING blade angle lookup]

After K loop (label 310):
  XFFT correction applied again
  Result: Blade angle depends on XFFT value during iteration
```

## The Problem

**For the same operating point, IW=1 and IW=2 should produce identical results** (since both modes should converge to the same solution: same CT, CP, blade angle, etc.).

But they don't because:

1. **IW=1 blade angle lookup uses CT directly** (unaffected by XFFT)
2. **IW=2 blade angle lookup uses CT adjusted by XFFT** during the secant iteration

When XFFT ≠ 1.0, this creates a **consistent error** in which blade angle is selected in IW=2.

## Why This Causes Errors

Example with XFFT = 0.95 (5% loss):

**IW=1:**
- Blade angle lookup: CTE = CT × AFCT × TCLI (uses original CT)
- Find BldAng correctly for this CT
- CP and CTN computed from correct blade angle

**IW=2:**
- Secant finds blade angle using CT_secant (with XFFT=0.95 entangled)
- CTE = CTN × AFCT × TCLI (where CTN ≈ CT×(1±XFFT correction))
- Blade angle may be WRONG because secant used different CT basis
- CP and CT mismatch with IW=1

## The Root Cause

In IW=2, the secant iteration solves:
```
CTA × XFFT = CT  (convergence equation)
CTA = CT / XFFT   (nominal solution with XFFT)
```

But the blade angle lookup should be done with the **plain CT value** (as in IW=1), not the XFFT-adjusted value.

## Suspected Fix

Move XFFT correction to AFTER the blade angle lookup in IW=2, matching IW=1's structure:

### Current (WRONG) IW=2:
```
Secant with XFFT inside K loop
  → blade angle selected using adjusted CT
Then XFFT correction after K loop
```

### Proposed (CORRECT) IW=2:
```
Secant WITHOUT XFFT inside K loop
  → blade angle selected using plain CT (same as IW=1)
Then XFFT correction after K loop (same location as IW=1)
```

This would require restructuring the secant iteration to:
1. Search for CTA such that CTA = CT (not CTA × XFFT = CT)
2. Use XFFT correction only in post-processing (label 310)
3. This matches IW=1's logic structurally

## Supporting Evidence

- IW=1 achieves ±0.1% accuracy
- IW=2 has 1-3% systematic error
- Error appears fundamental (not in secant formula or table lookup)
- Both should mathematically converge to identical solution for same operating point
- Asymmetric treatment of XFFT is the likely cause
