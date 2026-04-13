import numpy as np

def unint(N: int, XA, YA, X: float):
    """
    UNINT - Univariate interpolation with slope continuity (NASA CR-2066).
    Returns (Y, L) where L=0 normal, 1=below low end, 2=above high end.

    Accepts numpy arrays, lists, or any sequence for XA and YA.
    N must not exceed len(XA) / len(YA).
    """
    XA = np.asarray(XA, dtype=float)
    YA = np.asarray(YA, dtype=float)
    assert N <= len(XA), f"UNINT: N={N} exceeds XA length {len(XA)}"
    assert N <= len(YA), f"UNINT: N={N} exceeds YA length {len(YA)}"
    L = 0
    I = 1
    
    # Test for off low end
    if XA[0] - X > 0:
        L = 1
        return YA[0], L
    
    # Search for the interval
    for I in range(1, N):
        if XA[I] - X >= 0:
            break
    else:
        # Off high end
        L = 2
        return YA[N-1], L
    
    # Special handling for first and last intervals
    if I == 1:          # First interval
        JX1 = 0
        RA = 1.0
    elif I == N-1:      # Last interval
        JX1 = N-4
        RA = 0.0
    else:               # Normal middle interval
        JX1 = I - 2
        RA = (XA[I] - X) / (XA[I] - XA[I-1])
    
    RB = 1.0 - RA
    
    # Compute differences and interval lengths
    D = np.zeros(4)
    P = np.zeros(5)
    for J in range(3):
        P[J] = XA[JX1 + J + 1] - XA[JX1 + J]
        D[J] = X - XA[JX1 + J]
    D[3] = X - XA[JX1 + 3]
    P[3] = P[0] + P[1]
    P[4] = P[1] + P[2]
    
    # Final interpolation formula (exactly as in Fortran)
    Y = (YA[JX1]     * (RA / P[0]) * (D[1] / P[3]) * D[2] +
         YA[JX1 + 1] * (-RA / P[0]) * (D[0] / P[1]) * D[2] +
         YA[JX1 + 1] * (RB / P[1])  * (D[2] / P[4]) * D[3] +
         YA[JX1 + 2] * (RA / P[1])  * (D[0] / P[3]) * D[1] -
         YA[JX1 + 2] * (RB / P[1])  * (D[1] / P[2]) * D[3] +
         YA[JX1 + 3] * (RB / P[4])  * (D[1] / P[2]) * D[2])
    
    return Y, L