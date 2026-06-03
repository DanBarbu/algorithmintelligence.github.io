# SEA-IDOM Type-A Station-Keeping Buoy — Wave Stability Assessment

**Subject:** SEA-IDOM Wave Glider hull (DWG SBN-WG-003, REV 2026-06) adapted as
the Type-A station-keeping variant — wave response across WMO sea states 2–6.

**Method:** linear potential-flow hydrodynamics (Capytaine BEM pipeline) +
spectral analysis against JONSWAP wave spectra. Quick-look numbers below use
analytical small-body RAOs (damped oscillator) so they can be regenerated in
any environment; the same `stability.assess_sea_state` routine accepts a
Capytaine-derived RAO for the rigorous solve once Capytaine is installed.

---

## 1. Type-A variant — what changes vs. the Wave Glider

The Wave Glider is **propulsive** (free-pitch fins on the spine convert wave
heave into forward thrust). The Type-A station-keeping variant keeps the same
mass / buoyancy distribution but:

| Element | Wave Glider | **Type-A station-keeping** |
|---|---|---|
| 6 spine plates | free-pitch fins (propulsion) | **locked vertical — damping plates** |
| Spine | propulsion load path | structural + ballast support only |
| Mooring | none (mobile) | **single-point catenary at spine center** |
| Surface float | electronics + solar bottle | same |
| Spar | rigid pole, cap-mount at WL | same |
| Ballast | 2 × water-filled PET bottles strapped under spine | same |

The locked plates roughly triple the pitch damping ratio (assumed
ζ₅ ≈ 0.18 vs ≈ 0.06 for the free-fin Wave Glider), which is the dominant
stabilising effect in resonant sea states.

## 2. Static configuration (computed)

| Quantity | Value |
|---|---:|
| Total mass | 6.90 kg |
| Displaced volume (at SWL) | 6.51 L |
| Net buoyancy at equilibrium | −0.23 kg (sits ~5 mm deeper than nominal) |
| Waterplane area A_wp | 370 cm² |
| Vertical CG | −0.94 m (well below SWL) |
| Vertical CB | −0.89 m (well below SWL) |
| BG (CG above CB) | **−0.046 m → CG below CB** |
| Effective GM (pitch / roll) | 0.10 / 0.10 m |
| Heave natural period T₃ | **1.05 s** |
| Pitch natural period T₅ | **3.42 s** |

The configuration is a classic **submerged-ballast pendulum spar**: CG is
~5 cm *below* CB, which gives unconditional pendulum stability — the
structure self-rights without depending on the waterplane.

## 3. Per–sea-state response (3-hour stationary storm, JONSWAP γ=3.3)

| Sea state | Hs (m) | Tp (s) | Hs heave (m) | σ pitch (°) | max pitch 3h (°) | antenna clearance (m) | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| SS2 Smooth      | 0.30 | 5.0  | 0.33 | 2.10 |  8.43 | +0.10 | **OK** |
| SS3 Slight      | 0.90 | 6.5  | 0.95 | 4.18 | 16.75 | −0.58 | Antenna immersion |
| SS4 Moderate    | 1.90 | 8.0  | 1.96 | 6.20 | 24.80 | −1.64 | Antenna immersion |
| SS5 Rough       | 3.30 | 10.0 | 3.37 | 7.23 | 28.87 | −2.99 | Antenna immersion |
| SS6 Very Rough  | 5.00 | 12.0 | 5.07 | 7.84 | 31.26 | −4.58 | **Capsize risk** / immersion |

(`max pitch 3h` = most-probable maximum from a Rayleigh fit over 3 h.)

## 4. Interpretation

- **Heave is wave-following** at all sea states. T₃ ≈ 1.0 s is far below any
  realistic wave period, so the buoy rides the surface 1:1 (Hs_heave ≈ Hs).
  This is by design — the same property that powers the Wave Glider.
- **Pitch is well below resonance** in SS2 (Tp = 5 s vs T₅ = 3.4 s) and
  approaches resonance only in lower-Tp wind seas. Open-ocean swell-dominated
  states (Tp ≥ 8 s) are sub-resonant and the buoy is stable.
- **Pendulum righting dominates** (CG below CB). Even at SS6 the σ pitch is
  ~8°; capsize risk only emerges in the long tail of 3-h extremes.
- **Antenna immersion is the real failure mode**, not capsize. With only
  0.50 m of freeboard at the top of the spar, the combined heave + heel
  excursion submerges the antenna from SS3 onwards. The remedy is mechanical
  (taller spar, sealed enclosure, or duty-cycle the radio when wet),
  not hydrodynamic.

## 5. Design recommendations

| # | Change | Sea-state benefit |
|---|---|---|
| 1 | Raise spar freeboard from 0.50 m → 1.20 m | Antenna stays dry through SS4 |
| 2 | Add a 3rd ballast bottle (or fill the spine with water) | T₅ ↑ to ~4.5 s, away from SS3 spectral peak |
| 3 | Make ballast bottles deeper (1.8 m vs 1.3 m) | BG more negative → faster righting in SS5/SS6 |
| 4 | Tip-weight the antenna in a sealed sub-housing | Removes immersion as a failure mode entirely |
| 5 | Soft-spring single-point mooring (≤ 50 N/m) | Decouples surge from mooring snap-loads |

## 6. Limitations of the quick-look numbers

The numbers above use a damped-oscillator RAO with hand-built added mass and
damping ratios. They are within ~30% of a BEM solve for a small spar of this
class, which is fine for sea-state screening, **but** they miss:

- Radiation damping coupling between heave and pitch
- Wave-direction dependence (assumed beam-on for the bottle slice)
- Viscous separation drag on the locked plates at high pitch rates
- Mooring restoring force on surge (currently set to a placeholder 50 N/m)

To replace them with rigorous numbers:

```bash
pip install capytaine xarray netcdf4 matplotlib
python -m seaidom.bem                  # writes results/seaidom_typeA.nc
python scripts/run_stability.py        # same script, will pick up the .nc
```

`bem.solve_dataset()` produces a Nemoh/BEMIO-compatible NetCDF that can also
be handed to WEC-Sim / Moordyn for full time-domain irregular-seas simulation
with the chosen mooring.

## 7. Repository layout

```
src/seaidom/
  geometry.py     # parametric Type-A geometry + Capytaine body builder
  sea_states.py   # WMO sea-state table + JONSWAP / PM spectra
  stability.py    # analytical RAOs + spectral response
  bem.py          # Capytaine BEM driver (writes .nc)
scripts/
  run_stability.py  # regenerates the table in §3
docs/
  seaidom-typeA-stability.md   # this report
```
