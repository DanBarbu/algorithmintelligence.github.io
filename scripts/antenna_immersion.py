"""Verify the 60-s antenna-immersion thesis.

For each WMO sea state, compute the level-crossing statistics of the
relative wave-buoy motion  Y(t) = eta(t) - heave(t) crossing the freeboard
threshold. Report the mean immersion duration per event, the expected number
of events per 3-h storm, and the probability that any single immersion
exceeds 60 seconds.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from seaidom.geometry import TypeAGeometry                       # noqa: E402
from seaidom.sea_states import SEA_STATES                        # noqa: E402
from seaidom.stability import AnalyticalRAOs, antenna_immersion_analysis  # noqa: E402


def fmt_p(p: float) -> str:
    if p == 0:
        return "0"
    if p < 1e-9:
        return f"{p:.1e}"
    if p < 0.001:
        return f"{p:.2e}"
    if p < 1:
        return f"{p:.3f}"
    return f"{p:.2f}"


def fmt_t(t: float) -> str:
    if t == 0:
        return "—"
    if t < 0.1:
        return f"{t*1000:.0f} ms"
    if t < 60:
        return f"{t:.2f} s"
    if t < 3600:
        return f"{t/60:.1f} min"
    return f"{t/3600:.1f} h"


def report(label: str, geom: TypeAGeometry) -> str:
    rao = AnalyticalRAOs(geom)
    if not geom.is_statically_stable:
        return f"## {label}\n\nGeometry is statically UNSTABLE; immersion analysis skipped.\n"

    lines = [f"## {label}\n"]
    lines.append(f"- Spar freeboard h_fb = **{geom.spar_freeboard:.2f} m**")
    lines.append(f"- Heave Tn = **{rao.heave_natural_period():.2f} s**, "
                 f"pitch Tn = **{rao.pitch_natural_period():.2f} s**\n")

    lines.append(
        "| Sea state | Hs (m) | Tp (s) | σ_Y (cm) | σ_pitch (°) | "
        "P(wet) | events / 3 h | mean duration | P(event > 60 s) | "
        "P(>60 s in 3 h) | verdict |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for sea in SEA_STATES:
        r = antenna_immersion_analysis(rao, sea)
        survivable = r["p_storm_violation"] < 0.01
        verdict = "**OK** (no >60 s wetting)" if survivable else "**FAIL** (60 s thesis broken)"
        no_events = r["n_events_per_storm"] < 1e-12
        dur_str = "—" if no_events else fmt_t(r["mean_event_duration_s"])
        p_long_str = "—" if no_events else fmt_p(r["p_event_exceeds_survivable"])
        lines.append(
            f"| {sea.code} {sea.description} | {sea.hs:.2f} | {sea.tp:.1f} | "
            f"{r['sigma_y_m']*100:.2f} | {r['sigma_pitch_deg']:.2f} | "
            f"{fmt_p(r['p_wet_instant'])} | "
            f"{r['n_events_per_storm']:.2e} | "
            f"{dur_str} | {p_long_str} | "
            f"{fmt_p(r['p_storm_violation'])} | {verdict} |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    out_lines = [
        "# Antenna immersion duration — 60 s survivability check\n",
        "**Thesis:** the antenna survives any individual wetting that lasts ≤ 60 s.\n",
        "**Method:** stationary Gaussian level-crossing analysis (Rice formula) of "
        "the relative wave-buoy motion  Y(t) = η(t) − heave(t)  crossing the "
        "freeboard threshold h_fb. The buoy heave is wave-following at low ω "
        "(H₃ → 1), so Y has very low energy at the spectral peak and the antenna "
        "rides above the wave surface. Immersion events become possible only via "
        "the high-frequency residual where heave fails to follow.\n",
        "**Survivable** = probability of any single immersion exceeding 60 s in a "
        "3-hour storm is < 1%.\n",
        report("(A) Literal REV-B (water-filled hydrophone bottle, UNSTABLE)",
               TypeAGeometry()),
        report("(B) Recommended fix (5 kg pellet ballast + 4 L surface collar)",
               TypeAGeometry.recommended_fix()),
    ]
    text = "\n".join(out_lines)
    print(text)
    out = ROOT / "results" / "antenna_immersion.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


if __name__ == "__main__":
    main()
