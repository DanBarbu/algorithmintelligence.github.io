# Antenna immersion duration — 60 s survivability check

**Thesis:** the antenna survives any individual wetting that lasts ≤ 60 s.

**Method:** stationary Gaussian level-crossing analysis (Rice formula) of the relative wave-buoy motion  Y(t) = η(t) − heave(t)  crossing the freeboard threshold h_fb. The buoy heave is wave-following at low ω (H₃ → 1), so Y has very low energy at the spectral peak and the antenna rides above the wave surface. Immersion events become possible only via the high-frequency residual where heave fails to follow.

**Survivable** = probability of any single immersion exceeding 60 s in a 3-hour storm is < 1%.

## (A) Literal REV-B (water-filled hydrophone bottle, UNSTABLE)

Geometry is statically UNSTABLE; immersion analysis skipped.

## (B) Recommended fix (5 kg pellet ballast + 4 L surface collar)

- Spar freeboard h_fb = **1.50 m**
- Heave Tn = **1.07 s**, pitch Tn = **4.04 s**

| Sea state | Hs (m) | Tp (s) | σ_Y (cm) | σ_pitch (°) | P(wet) | events / 3 h | mean duration | P(event > 60 s) | P(>60 s in 3 h) | verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| SS2 Smooth | 0.30 | 5.0 | 1.89 | 1.94 | 0 | 0.00e+00 | — | — | 0 | **OK** (no >60 s wetting) |
| SS3 Slight | 0.90 | 6.5 | 3.48 | 3.91 | 0 | 0.00e+00 | — | — | 0 | **OK** (no >60 s wetting) |
| SS4 Moderate | 1.90 | 8.0 | 4.99 | 5.91 | 2.2e-196 | 1.43e-190 | — | — | 0 | **OK** (no >60 s wetting) |
| SS5 Rough | 3.30 | 10.0 | 5.78 | 6.99 | 1.3e-146 | 6.77e-141 | — | — | 0 | **OK** (no >60 s wetting) |
| SS6 Very Rough | 5.00 | 12.0 | 6.34 | 7.63 | 4.4e-122 | 2.06e-116 | — | — | 0 | **OK** (no >60 s wetting) |
