# SEA-IDOM Type-A Station-Keeping Buoy — Wave Stability Assessment

**Subject:** SEA-IDOM Type-A station-keeping variant, revision **REV-B**:
3 m spar, 1.5 m freeboard, 6 locked PET damping plates on the spine, 2 spine-
strapped water-filled ballast bottles, plus a **3rd ballast bottle housing a
hydrophone, rope-tethered 2 m below the spar tip** (z = −3.5 m).

**Method:** linear potential-flow hydrodynamics (Capytaine BEM pipeline) +
spectral analysis against JONSWAP wave spectra. Quick-look numbers below use
analytical small-body RAOs so they reproduce in any environment; the same
`stability.assess_sea_state` routine accepts a Capytaine-derived RAO as a
drop-in replacement for the rigorous solve.

---

## 1. REV-B geometry (literal proposal)

| Element | Value |
|---|---|
| Spar total length | **3.00 m** |
| Spar freeboard | **1.50 m** (submerged length 1.50 m) |
| Spine attachment | **z = −1.50 m** (at the spar tip) |
| 6 locked PET damping plates | on the spine, free-pitch disabled |
| 2 spine ballast bottles | water-filled, 2 kg each at z = −1.50 m |
| 3rd "ballast" bottle | water-filled around hydrophone, **~2.2 kg, 2 L** |
| 3rd bottle attachment | **2 m rope from spar tip → z = −3.5 m** |

## 2. Static stability — **the literal REV-B proposal is unstable**

| Quantity | Value |
|---|---:|
| Total mass | 9.90 kg |
| Displaced volume | 8.65 L (net buoyancy −1.03 kg) |
| Vertical CG | −1.48 m |
| Vertical CB | −1.60 m |
| **GM_L (pitch)** | **−0.08 m** |
| **GM_T (roll)** | **−0.11 m** |
| Static stability | **UNSTABLE — capsizes at rest** |

**Why.** Lengthening the spar to 3 m and pulling the freeboard up to 1.5 m
adds 0.8 kg of structural mass with its centre at the SWL (the midpoint of
a 3 m bar with 1.5 m freeboard is at z = 0). That pushes the system CG
upward. The 2.2 kg rope-tethered bottle is **nearly neutrally buoyant**
(2.2 kg mass vs 2.05 kg of displaced sea water → net weight only ~1.5 N),
so even with a 2 m pendulum arm it provides ≪ 1% of the righting moment
the new freeboard demands.

**No sea-state response is meaningful for an unstable hull** — it would
roll over before wave forcing matters.

## 3. Recommended fix — minimum changes to make REV-B work

Two changes to the literal proposal restore static stability **and** keep the
buoy floating:

1. **Pellet-ballast the hydrophone bottle to ~5 kg.** Hydrophone (~0.5 kg) +
   water + ~3 kg of lead/steel shot or sand around the sensor inside the
   sealed 2 L bottle. Net weight in water rises from 1.5 N → ~30 N,
   giving the 2 m pendulum a meaningful righting moment.
2. **Add a sealed 4 L surface flotation collar at the SWL** (e.g., a foam-
   filled HDPE collar around the electronics bottle, or a second sealed
   2 L PET float in tandem). The extra ~3 kg of ballast would otherwise
   sink the buoy; the collar restores net positive buoyancy.

### Static configuration with the fix

| Quantity | Value |
|---|---:|
| Total mass | 13.20 kg |
| Displaced volume | 10.65 L (trims by ~5 cm additional immersion) |
| Waterplane area A_wp | 684 cm² |
| Vertical CG | −1.85 m |
| Vertical CB | −1.31 m |
| **GM_L (pitch)** | **+0.58 m** |
| **GM_T (roll)** | **+0.55 m** |
| Static stability | **STABLE** |
| Heave natural period T₃ | 1.07 s |
| Pitch natural period T₅ | 4.04 s |

## 4. Per–sea-state response (recommended fix, 3-h JONSWAP γ=3.3)

| Sea state | Hs (m) | Tp (s) | Hs heave (m) | σ pitch (°) | max pitch 3 h (°) | antenna clearance (m) | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| SS2 Smooth      | 0.30 | 5.0  | 0.33 | 1.9 |  7.7 | +0.97 | **OK** |
| SS3 Slight      | 0.90 | 6.5  | 0.95 | 3.9 | 15.5 | +0.15 | **OK** |
| SS4 Moderate    | 1.90 | 8.0  | 1.97 | 5.9 | 23.4 | −1.06 | Antenna immersion |
| SS5 Rough       | 3.30 | 10.0 | 3.37 | 7.0 | 27.7 | −2.51 | Antenna immersion |
| SS6 Very Rough  | 5.00 | 12.0 | 5.08 | 7.6 | 30.2 | −4.16 | **Capsize risk** / immersion |

### Comparison vs REV-A (1.8 m spar, 0.5 m freeboard, no hydrophone bottle)

| Sea state | Antenna clearance — REV-A | **REV-B fix** | Improvement |
|---|---:|---:|---|
| SS2 | +0.10 m | **+0.97 m** | +0.87 m |
| SS3 | −0.58 m | **+0.15 m** | now dry |
| SS4 | −1.64 m | **−1.06 m** | +0.58 m |
| SS5 | −2.99 m | **−2.51 m** | +0.48 m |
| SS6 | −4.58 m | **−4.16 m** | +0.42 m |

REV-B with the recommended fix keeps the antenna **dry through SS3** (vs
SS2 for REV-A) and reduces pitch extremes 5–10% across the board thanks to
the longer pendulum arm and higher GM.

## 5. Interpretation

- **Heave is wave-following** at every sea state (T₃ ≈ 1 s ≪ Tp). The buoy
  rides the surface 1:1 — by design, same as the Wave Glider.
- **Pitch resonance is shifted out of the open-ocean swell band.**
  T₅ = 4.0 s for the fixed REV-B vs Tp ≥ 8 s for SS4–SS6, so the spectral
  peak sits well above the natural frequency and pitch motions stay sub-
  resonant in the regimes that dominate at sea.
- **Antenna immersion is the limiting failure mode** above SS3. With 1.5 m
  of freeboard (already 3× the REV-A value), the combined heave + heel
  excursion still submerges the antenna in moderate-and-up seas. The remedy
  is mechanical (sealed antenna pod, taller spar, or RF duty-cycling when
  wet), not hydrodynamic.
- **Marginal capsize risk at SS6 only.** Most-probable 3-h max pitch of
  30.2° sits right at the rule-of-thumb capsize threshold; for routine
  operation at SS6 a further GM increase (deeper hydrophone bottle, e.g.
  3 m rope instead of 2 m) buys margin.

## 6. Reproducing the numbers

```bash
# A) Literal REV-B proposal and B) Recommended fix, side by side:
python scripts/run_stability.py

# Rigorous BEM (once Capytaine is installed):
pip install capytaine xarray netcdf4 matplotlib
python -m seaidom.bem                       # writes results/seaidom_typeA.nc
python scripts/run_stability.py             # picks up the .nc if present
```

`bem.solve_dataset()` produces a Nemoh/BEMIO-compatible NetCDF that can also
be handed to WEC-Sim / Moordyn for full time-domain irregular-seas simulation
with the chosen mooring (single-point catenary at the spine center).

## 7. Repository layout

```
src/seaidom/
  geometry.py     # parametric REV-B geometry + Capytaine body builder
  sea_states.py   # WMO sea-state table + JONSWAP / PM spectra
  stability.py    # analytical RAOs + spectral response
  bem.py          # Capytaine BEM driver (writes .nc)
scripts/
  run_stability.py  # prints sections A and B
docs/
  seaidom-typeA-stability.md   # this report
```
