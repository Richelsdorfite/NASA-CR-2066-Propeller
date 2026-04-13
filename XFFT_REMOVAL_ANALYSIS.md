# IW=2 XFFT Removal Fix - Results Analysis

## Changes Applied

1. **Line 386:** Changed `CTA1[KJ] = CT - CTA[KJ] * XFFT[KL]` to `CTA1[KJ] = CT - CTA[KJ]`
   - Removes XFFT from convergence equation
   - Secant now solves for CTA = CT directly

2. **Line 398:** Changed `CTN[KL] = CTA[NFTX] / XFFT[KL]` to `CTN[KL] = CTA[NFTX]`
   - Removes division by XFFT
   - Uses un-corrected CTA value

## Effect of Changes

**Theoretical expectation:** Since XFFT = 1.0 for all test cases, both formulations should be equivalent:
- Original: `CTA × 1.0 = CT` → `CTA = CT` → `CTN = CTA / 1.0 = CT`
- Modified: `CTA = CT` → `CTN = CTA = CT`

**Result:** Mathematically equivalent when XFFT = 1.0, so no significant change expected.

## Actual Results

Errors **slightly increased** in most cases:
```
IC 1: 0.48% → 0.51% (worse by 0.03%)
IC 2: 2.17% → 2.30% (worse by 0.13%)
IC 3: 3.09% → 3.16% (worse by 0.07%)
IC 6: 1.77% → 1.84% (worse by 0.07%)
IC 7: 2.45% → 2.49% (worse by 0.04%)
```

Average error slightly increased from ~1.76% to ~1.81%

## Why The Fix Didn't Help

### Possible Reasons:

1. **XFFT = 1.0 for all test cases**
   - The asymmetry fix only matters when XFFT ≠ 1.0
   - For this test data, XFFT is always computed as 1.0
   - Therefore, removing XFFT has minimal effect

2. **The secant iteration convergence behavior changed**
   - With original equation: CTA1[KJ] = CT - CTA[KJ] × 1.0 = 0 immediately
   - With new equation: CTA1[KJ] = CT - CTA[KJ] = 0 immediately
   - Both converge at first iteration, but rounding may differ

3. **Rounding errors from iteration**
   - The secant formula computes subsequent iterations even after convergence
   - Different convergence equations may accumulate errors differently

4. **The 1-3% error is not from XFFT asymmetry**
   - The error persists even after removing XFFT from the iteration
   - Root cause is likely something else in the IW=2 calculation path

## Conclusion

**The fix doesn't solve the IW=2 accuracy problem** for the test cases where XFFT = 1.0. This suggests:

1. The XFFT asymmetry is a theoretical correctness issue, but not the cause of observed 1-3% error
2. The 1-3% IW=2 error has a different root cause
3. For test data where XFFT ≠ 1.0, this fix might be important for correctness even if it doesn't fix the 1-3% error

## Next Steps To Investigate

1. **Determine if error is inherent to IW=2 algorithm**
   - Run the same test against original Fortran code
   - If Fortran also has 1-3% error in IW=2, the algorithm has this limitation

2. **Check other IW=2 calculation stages**
   - Look for similar XFFT handling elsewhere
   - Check if CT/CP derivation after blade angle lookup is correct
   - Review post-processing at label 310 and beyond

3. **Test with non-unity XFFT values**
   - Use operating conditions where XFFT ≠ 1.0
   - Verify this fix improves accuracy for those cases

## Decision Point

Should we:
- **Keep the fix** (it's theoretically more correct and may help for non-unity XFFT)
- **Revert the fix** (doesn't help current tests and slightly worsens accuracy)
- **Investigate other sources** of the 1-3% IW=2 error
