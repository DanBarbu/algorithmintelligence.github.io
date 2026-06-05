# SEA-IDOM Type-A — Top-10 Feasibility & Survivability Risk Register

**Scope:** 5-year operational deployment of the Type-A station-keeping buoy
(REV-B with the recommended fix from `docs/seaidom-typeA-stability.md`),
manufactured at fleet scale (hundreds to thousands of units/year), single-
point moored in open-ocean conditions up to SS6.

**Scoring rubric.** Score = Likelihood × Impact.

| Code | Likelihood | Code | Impact |
|---|---|---|---|
| 1 | rare (<1% over 5 yr) | 1 | negligible (no mission effect) |
| 2 | unlikely (1–10%) | 2 | minor (degraded data) |
| 3 | possible (10–50%) | 3 | moderate (partial loss) |
| 4 | likely (50–90%) | 4 | major (mission loss for that unit) |
| 5 | almost certain (>90%) | 5 | catastrophic (fleet recall / regulatory) |

---

## Top-10 risks (sorted by score)

| # | Risk | Category | L | I | Score | Primary mitigation |
|---|---|---|---:|---:|---:|---|
| 1 | **3D-printed TrussFab connector hydrolysis / UV embrittlement** | Materials | 5 | 5 | **25** | Print in marine-grade material (PETG-CF, NylonX, PA12 SLS, or stainless 316L MIM); UV-stabilise resin; design joints with mechanical interlock so degraded polymer still constrains geometry |
| 2 | **Biofouling growth changing mass, drag, and natural periods** | Operations | 5 | 4 | **20** | Foul-release silicone coating (Intersleek 1100SR), copper-impregnated PET wrap, scheduled cleaning at 12-mo intervals, accept 20% trim margin in design |
| 3 | **PET cap-seal failure → electronics water ingress** | Materials | 4 | 5 | **20** | Replace OE cap with double O-ring screw-cap + nitrile gasket; potted electronics; humidity sensor + automatic radio-silent on detect; pressure-equalising vent valve |
| 4 | **Surface-PET UV embrittlement (50% strength loss / 12–24 mo)** | Materials | 5 | 4 | **20** | UV-opaque overwrap (HDPE sleeve or paint with TiO₂ + carbon-black); rotate fleet at ~24 mo refurb interval; design surface bottle as replaceable LRU |
| 5 | **Battery cycle-life ceiling over 5 yr** | Power | 4 | 4 | **16** | LiFePO4 (3000–5000 cycles vs 1000 for LiPo); MPPT solar with 3× nameplate solar oversize; sleep-mode duty-cycling driven by mission profile; quarterly state-of-health telemetry |
| 6 | **Microplastic shedding & regulatory exposure (EU SUP, MARPOL Annex V)** | Regulatory | 4 | 4 | **16** | Treat PET externally with silicone-acrylic coating to suppress shedding; declare unit as recoverable equipment with serial-tracked deployment register; budget end-of-life recovery as mandatory |
| 7 | **Single-point mooring failure (line abrasion, anchor drag, kelp wrap)** | Mooring | 3 | 5 | **15** | Two-leg catenary with redundancy; Kevlar core inside polyester jacket; rotating swivel at fairlead; AIS-A transponder for drift recovery; over-spec anchor (Stevpris ≥ 5× hold) |
| 8 | **Manufacturing variance of off-the-shelf PET bottles → trim drift** | Manufacturing | 5 | 3 | **15** | Don't use OE bottles — qualify ONE blow-moulded SKU (custom or single-vendor Coca-Cola spec); weigh each bottle into 5 mass bins; randomise bin assignment so trim averages out per buoy; QA reject > ±3σ |
| 9 | **PET wall fatigue / creep under cyclic wave loading (~3×10⁸ cycles/5 yr)** | Materials | 3 | 4 | **12** | Bi-orient PET vs amorphous (cap region); double-skin ballast bottles (sealed air gap inside water-fill) so a leak doesn't sink the unit; pre-deployment burst test at 4× working pressure |
| 10 | **Capsize from rogue waves / breaking seas above SS6** | Hydrodynamic | 2 | 5 | **10** | Extend hydrophone-bottle rope 2 m → 3 m (longer pendulum); raise pellet mass 5 → 6 kg; add inverted-orientation tilt switch → emergency-recover beacon; self-righting hull skirt as next-rev option |

---

## Risk heatmap

```
Impact →   1     2     3     4     5
       ┌─────┬─────┬─────┬─────┬─────┐
   5   │     │     │  #8 │ #2,4│  #1 │
       ├─────┼─────┼─────┼─────┼─────┤
   4   │     │     │     │ #5,6│ #3  │
       ├─────┼─────┼─────┼─────┼─────┤
   3   │     │     │     │ #9  │ #7  │
       ├─────┼─────┼─────┼─────┼─────┤
   2   │     │     │     │     │ #10 │
       ├─────┼─────┼─────┼─────┼─────┤
   1   │     │     │     │     │     │
       └─────┴─────┴─────┴─────┴─────┘
        L↑
```

Five risks (#1 #2 #3 #4 #7) sit in the high-impact/high-likelihood zone and
will dominate the certification effort. Four (#5 #6 #8 #9) are program-level
issues — solvable with budget and process discipline. #10 is the only purely
hydrodynamic survivability item, and it is already addressable inside the
current geometry envelope.

---

## Detailed mitigations by risk

### #1 — 3D-printed connector degradation (the project killer)

The TrussFab hub is the **structural backbone** of the whole buoy. Standard
hobbyist materials are non-starters for 5-year submersion:

| Material | 5-yr submersion outlook | Verdict |
|---|---|---|
| PLA | Hydrolyses in weeks at 25 °C | **No** |
| ABS | UV-embrittles in months | **No** |
| PETG | Better than PLA, fatigues at submerged joints | Marginal |
| ASA | UV-stable but mediocre wet creep | Marginal |
| PA12 (SLS) | Good chemistry, moderate UV | **Yes** with overcoat |
| PETG-CF / NylonX | Best printable option | **Yes** |
| Stainless 316L MIM | Pricier, lasts indefinitely | **Yes** (premium tier) |

**Recommendation:** dual-source — PA12 SLS for prototype/low-volume,
investment-cast or MIM 316L for production runs > 500 units/yr. The TrussFab
geometry transfers to both.

### #2 — Biofouling

Foul-release coatings prevent firm adhesion but don't stop initial settlement.
After 12 months an uncoated PET surface in temperate water typically grows
~5 kg/m² of biomass → for a 0.5 m² wetted surface, +2.5 kg of added mass.
That alone would sink the literal REV-B (which only has 1 kg net buoyancy
margin in the recommended fix).

**Budget the biofouling mass in the buoyancy reserve.** Recommendation: size
the surface collar so the unit still has +2 kg net buoyancy *after* 2 years
of biofouling.

### #3 — Cap-seal failure

The OE PET cap is designed for shelf life with carbonated drink pressure, not
12-hour cyclic wave loading × 1800 days. The screw thread fatigues. A double
O-ring cap mount through the TrussFab connector is non-negotiable for any
serious deployment.

### #5 — Battery cycle-life

LiFePO4 16Ah at 3.2 V → 51 Wh. A 10 W solar at 15% effective duty → 36 Wh/day.
At a 1 W average load this comfortably charges. The risk is calendar-loss
(~20% over 5 yr) and deep-discharge cycles in winter at high latitudes.
Mitigate by enforced load shedding below 30% SoC.

### #6 — Microplastic & regulatory

The EU Single-Use Plastics Directive and MARPOL Annex V already cover this
class of equipment. A serial-tracked deployment register and mandatory
recovery-or-replace at 30 mo is required to avoid being classed as an
unrecoverable ocean polluter. **Plan recovery into the unit BOM, not as an
afterthought.**

### #8 — PET bottle variance

OE bottles vary ±15% in wall thickness and ±10% in tare mass. At fleet scale,
that compounds into 100s of grams of trim variation per buoy. Either:

- Qualify ONE custom PET SKU from a single vendor with QC at ±2% (adds
  $/unit but solves the problem), or
- Weigh & sort incoming bottles into mass bins, assign one bin per buoy
  position so the variance averages out per assembly.

The first is cleaner; the second is faster to start.

---

## Items deliberately NOT in the top-10 (and why)

| Excluded risk | Reason |
|---|---|
| Lightning strike on antenna | Catastrophic but very rare (~10⁻³/yr in tropics, lower elsewhere); cheaper to insure than to design out |
| Vessel collision | Mitigated by AIS-A transponder (already in #7) |
| Hydrophone calibration drift | Sensor-vendor responsibility; replace at 30-mo refurb |
| Solar-panel delamination | Subset of #4 (UV) and #3 (seal); already mitigated |
| Wildlife entanglement (rope tether) | Use marine-mammal-safe weak-link in the rope; low recurrence |
| Theft | Open-ocean deployment limits exposure; AIS already mitigates |
| Spar buckling | 30 mm HDPE spar under axial wave loading is well within yield; verify by FEA at design freeze, not a survivability risk |

---

## Manufacturing scale-up risk path

| Volume / yr | Dominant risk | Action |
|---|---|---|
| 1–10 | Material qualification (#1) | Print PA12, ASTM seawater immersion test |
| 10–100 | Bottle variance (#8), QA process | Single-SKU contract with bottle vendor |
| 100–1000 | Throughput on connectors (#1) | Switch PA12 → MIM 316L; partner with foundry |
| 1000+ | Regulatory (#6), recovery logistics | Lease recovery vessels, fleet AIS network |

---

## Bottom-line feasibility verdict

**Hydrodynamically the design works.** Stability and antenna immersion are
solved by the recommended fix in `seaidom-typeA-stability.md`.

**Material durability is the dominant 5-year survivability risk.** Three of
the top four scores (#1, #3, #4) are all polymer degradation. None of them
are showstoppers — they are *engineering choices* to upgrade materials and
embrace a 24-month refurb cycle — but they are non-negotiable line items in
the BOM and operating cost model.

**At fleet scale, recovery logistics and regulatory compliance (#6) will
likely dominate operating cost**, more than manufacturing itself.
