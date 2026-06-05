# SEA-IDOM Type-A — Sprayable Coating System Specification

**Goal:** one sprayable, marine-grade coating *stack* applied after final
assembly that simultaneously mitigates the top-4 risks identified in
`seaidom-typeA-risk-register.md`:

| # | Risk | What the coating must do |
|---|---|---|
| 1 | 3D-printed hub hydrolysis / UV embrittlement | Water-vapour barrier + UV block |
| 2 | Biofouling growth | Foul-release (FR), 5-yr-clean class |
| 3 | PET cap-seal failure → water ingress | Monolithic over-seal across cap-bottle joint |
| 4 | Surface PET UV embrittlement | UV-opaque outer film |

A single foul-release topcoat over an epoxy barrier primer hits all four
boxes. The recommended stack and a budget alternative are below.

---

## 1. Recommended system — Intersleek 1100SR 3-coat stack (AkzoNobel)

The same system specified on cruise-ship and naval-vessel hulls; documented
5-year clean service in tropical waters. PFAS-free since 2024 reformulation.

| Layer | Product | DFT (µm) | Function |
|---|---|---:|---|
| 0 — pretreatment (PET parts only) | **Chlorinated polyolefin (CPO) adhesion promoter** — 3M PR40 or Bondrite CP-30 | 5–10 | Overcomes PET's 42 mN/m surface energy |
| 1 — barrier primer | **Intershield 300** epoxy-amine | 150 | Water-vapour barrier; bonds to 3D-printed PA12/PETG and to CPO-treated PET |
| 2 — tie coat | **Intersleek 731** silicone elastomer | 100 | Couples epoxy to silicone topcoat |
| 3 — topcoat | **Intersleek 1100SR** fluorinated-silicone foul-release | 150 | UV-opaque (pigmented), foul-release, 5+ yr |
| **Total** | | **~415 µm** | |

**Material cost (at fleet scale, 2026 €/m²):** ≈ 65–90 €/m² for the full
stack. Per buoy wetted area ≈ 0.7 m² → ≈ 50 € of coating per unit.

### Why this solves each top-4 risk

| Risk | How the stack solves it |
|---|---|
| **#1 — Hub hydrolysis/UV** | Intershield 300 is a 150 µm continuous epoxy barrier — water-vapour transmission rate < 1 g/(m²·day), which is the order-of-magnitude reduction needed to take PA12 hydrolysis from a 2-yr issue to a >10-yr non-issue. The silicone topcoats above also screen UV (transmittance ≈ 0 at 300–400 nm for pigmented PDMS). |
| **#2 — Biofouling** | Intersleek 1100SR is the reference foul-release coating; documented self-cleaning above 8 kn flow and manual-wipe at zero-flow. For a station-keeping buoy with low flow, plan one wipe at 24 mo, full recoat at 5 yr. |
| **#3 — Cap seal redundancy** | Spray the assembled buoy *after* final cap torque. The 150 + 100 + 150 µm layers form a monolithic film bridging the cap-bottle interface — a *redundant single-use seal* backing up the mechanical O-ring. Field-removable with a heat gun + scraper at scheduled refurb. |
| **#4 — Surface PET UV** | Pigmented PDMS topcoat blocks 100% of UV-B/UV-C and >95% of UV-A. The PET underneath sees indoor-equivalent radiation → predicted half-life of mechanical properties extends from 18 mo to >10 yr. |

---

## 2. Application procedure for the SEA-IDOM Type-A

The stack works as a **single post-assembly process step**. Sequence:

1. Final mechanical assembly of all components (spar, spine, fins, bottles,
   ballast, hydrophone-in-bottle, surface float, antenna pod).
2. Torque all cap connectors to spec; install all O-rings.
3. Mask: antenna RF window, solar-panel surface, hydrophone diaphragm,
   ventilation valves, mooring fairlead.
4. Hang the buoy on a rotating jig.
5. PET surface flame-treat OR CPO wipe — increases surface energy from
   42 → > 60 mN/m for epoxy adhesion.
6. Spray Intershield 300 (HVLP, two passes orthogonal), cure 6 h at 25 °C.
7. Spray Intersleek 731 tie coat (single pass), cure 8 h.
8. Spray Intersleek 1100SR topcoat (two passes orthogonal), cure 24 h at 25 °C.
9. Remove masks, post-cure 7 days before submersion.

Throughput at fleet scale: ~6 buoys per booth-day, single 8-hour shift.

---

## 3. Budget alternative (1–2 yr foul-release, easier application)

For prototype / low-volume runs where the Intersleek booth process is not
yet justified:

| Layer | Product | DFT (µm) | Notes |
|---|---|---:|---|
| 1 — barrier primer | **Awlgrip 545 epoxy primer** | 100 | Easier spray, marine-grade |
| 2 — UV topcoat | **Awlgrip Topcoat 2-part PU** | 75 | UV-stable pigmented PU |
| 3 — foul-release | **Sea Hawk Mission Bay** silicone FR | 100 | 1–2 yr foul-release at low flow |

Cost ≈ 25 €/m², ≈ 18 € per buoy.

Trade-off: **half the service life of the Intersleek stack** — drives a
24-month refurb cycle. Acceptable for prototyping and trials; switch to
Intersleek for production runs > 100 units.

---

## 4. Newer alternatives worth tracking (not yet recommended)

- **Hempel Hempaguard MaX** — fluorine-free hydrogel + silicone hybrid.
  Comparable claims to Intersleek, 5-yr clean. Younger field record.
- **PPG Sigmaglide 2390** — second-generation fluorine-free FR. Strong
  ship trials but limited marine-instrumentation data.
- **Selektope-loaded silicones** (I-Tech AB) — biocide-based; effective but
  introduces regulatory complexity (biocide registration per jurisdiction)
  that conflicts with risk #6.

Re-evaluate annually as field data accumulates.

---

## 5. Caveats and constraints

- **PFAS regulations.** Confirm the *current* Intersleek 1100SR formulation
  is PFAS-free before specifying for EU deployments — AkzoNobel reformulated
  in 2024 but stock dates matter.
- **Cap mechanical integrity is unchanged.** The coating is a *redundant*
  seal; the double O-ring cap (risk #3 mitigation) is still mandatory.
  The coating film alone is not rated as a primary pressure seal.
- **Antenna RF window.** PDMS is RF-transparent at L/S/UHF, but coating
  thickness adds dielectric loading. Mask the radome or validate VSWR
  post-coating before flight.
- **Solar-panel surface.** Must be masked — silicone topcoat would
  attenuate ~5–10% of usable spectrum.
- **Recoat at 5 yr.** Plan removal with heated air at 80–100 °C and
  mechanical scrape, then re-spray the full stack. Budget into the
  refurb cycle in the operating cost model.

---

## 6. Risk-register impact

Applying this stack moves the top-4 risks as follows:

| # | Pre-coating L × I | Post-coating L × I | Change |
|---|---:|---:|---|
| 1 | 5 × 5 = **25** | 2 × 4 = **8** | epoxy barrier + UV block |
| 2 | 5 × 4 = **20** | 2 × 3 = **6** | 5-yr foul-release |
| 3 | 4 × 5 = **20** | 2 × 4 = **8** | redundant over-seal on assembly |
| 4 | 5 × 4 = **20** | 2 × 3 = **6** | UV-opaque topcoat |

Aggregate top-4 score: **85 → 28** (a 67% reduction in the dominant
survivability risk pool) for ≈ 50 € of materials per unit.

The next-highest risk after coating becomes **#5 battery cycle-life** —
which becomes the new headline survivability constraint.
