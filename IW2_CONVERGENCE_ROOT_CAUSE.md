# IW=2 Convergence Analysis - Root Cause Found

## CRITICAL ISSUE: Secant Method Never Executes

### The Problem
The entire secant iteration loop in PERFM.py (IW=2 path) **exits immediately at KJ=0** without actually iterating. This causes the algorithm to use only the initial guess instead of refining it through iteration.

### Root Cause: DMN Calculation

**Current Code (lines 374-384):**
```python
if ZJJ[K] == 0.0:
    ZMCRT = ZMCRO[NNCLT]
    DMN = ZMS[1] - ZMCRT
else:
    ZMCRT, _ = unint(11, ZJCL, ZMCRL[NNCLT], ZJJ[K])
    DMN = ZMS[0] - ZMCRT
XFFT[KL] = 1.0
if DMN > 0.0:                    # <-- THIS CONDITION IS NEVER MET!
    CTE2 = CTE1 * TXCLI[KL] / TFCLI[K]
    XFFT[KL], _ = biquad(ZMMMC.tolist(), 0, DMN, CTE2)
```

### Why It Fails

1. **DMN is always NEGATIVE:**
   - Example values from trace: -0.142, -0.032, -0.168, -0.279, -0.231, etc.
   - This occurs because DMN = ZMS[...] - ZMCRT, and the subtraction yields negative values

2. **biquad() is never called:**
   - The condition `if DMN > 0.0:` is false for all test cases
   - XFFT[KL] **remains at default value 1.0**

3. **Residual becomes exactly zero:**
   ```
   CTA1[0] = CT - CTA[0] * XFFT[KL]
           = CT - CT * 1.0  
           = 0.0             <-- EXACTLY ZERO!
   ```

4. **Immediate exit triggers:**
   ```python
   if CTA1[0] == 0.0 and KJ == 0:
       break  # <-- Exit at first iteration!
   ```

5. **Algorithm uses initial guess only:**
   - Result: CTN[KL] = CTA[NFTX] / XFFT[KL] = CTA[0] / 1.0 = CT (initial guess)
   - No refinement through iteration occurs

### Impact on Accuracy

- **CT computation:** Uses only CTA[0] = CT, no iteration
  - Result: CT is roughly correct because the initial guess is reasonable
  - Remaining error comes from using XFFT=1.0 instead of computed value
  
- **CP and SHP computation:** Depends on the unrefined CT value
  - Result: 2-3% errors for most operating points (as observed in tests)

### The Fix Required

The condition on line 382 needs to be corrected to handle negative DMN. Options:

**Option 1: Check absolute value**
```python
if abs(DMN) > threshold:
    CTE2 = CTE1 * TXCLI[KL] / TFCLI[K]
    XFFT[KL], _ = biquad(ZMMMC.tolist(), 0, DMN, CTE2)
```

**Option 2: Always compute (remove condition)**
```python
CTE2 = CTE1 * TXCLI[KL] / TFCLI[K]
XFFT[KL], _ = biquad(ZMMMC.tolist(), 0, DMN, CTE2)
```

**Option 3: Check sign and adjust calculation**
- Determine if DMN sign is intentional or a calculation error

### Verification Needed

1. Check original Fortran code: Does it have the same condition or does it always compute XFFT?
2. Understand the physical meaning of DMN to determine correct fix
3. Test the fix to validate convergence and accuracy improvement

## Test Evidence

All 16 IW=2 cases (from Condition N°2) exit immediately with:
- DMN < 0.0 (always negative)
- XFFT = 1.0 (default, never computed)
- CTA1[0] = 0.0 (forces exit)
- No subsequent iterations occur
