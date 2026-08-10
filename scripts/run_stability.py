"""Run the analytical spectral stability sweep for SEA-IDOM Type-A.

Prints two markdown sections to stdout:
  (A) Literal REV-B proposal (3 m spar, 1.5 m freeboard, rope-tethered
      water-filled hydrophone bottle at z = -3.5 m).
  (B) Recommended fix: pellet-ballast the hydrophone bottle to 5 kg and
      add a 4 L sealed surface flotation collar.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import io           # noqa: E402
import numpy as np  # noqa: E402

from seaidom.geometry import TypeAGeometry  # noqa: E402
from seaidom.sea_states import SEA_STATES   # noqa: E402
from seaidom.stability import AnalyticalRAOs, assess_sea_state  # noqa: E402


def fmt(x, d=2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or not np.isfinite(x))):
        return "—"
    return f"{x:.{d}f}"


def report(geom: TypeAGeometry, title: str, stream) -> None:
    rao = AnalyticalRAOs(geom)
    gm_L, gm_T = geom.gm()
    print(f"## {title}\n", file=stream)
    print(f"- Total mass: **{geom.total_mass:.2f} kg**", file=stream)
    print(f"- Displaced volume: **{geom.displaced_volume*1e3:.2f} L** "
          f"(net buoyancy {geom.displaced_volume*1025 - geom.total_mass:+.2f} kg)",
          file=stream)
    print(f"- Waterplane area A_wp: **{geom.waterplane_area*1e4:.1f} cm²**",
          file=stream)
    print(f"- Vertical CG (z): **{geom.vertical_cg:+.3f} m**", file=stream)
    print(f"- Vertical CB (z): **{geom.vertical_cb:+.3f} m**", file=stream)
    print(f"- GM_L / GM_T: **{gm_L:+.3f} / {gm_T:+.3f} m**  "
          f"→ static stability: **{'STABLE' if geom.is_statically_stable else 'UNSTABLE'}**",
          file=stream)
    print(f"- Heave Tn: **{rao.heave_natural_period():.2f} s**", file=stream)
    tp5 = rao.pitch_natural_period()
    tp5_s = f"{tp5:.2f} s" if tp5 == tp5 else "— (unstable)"
    print(f"- Pitch Tn: **{tp5_s}**\n", file=stream)

    print("| Sea state | Hs (m) | Tp (s) | "
          "Hs heave (m) | σ pitch (°) | max pitch 3h (°) | "
          "antenna clearance (m) | verdict |", file=stream)
    print("|---|---:|---:|---:|---:|---:|---:|---|", file=stream)

    for sea in SEA_STATES:
        res = assess_sea_state(rao, sea)
        print(
            f"| {sea.code} {sea.description} | {sea.hs:.2f} | {sea.tp:.1f} | "
            f"{fmt(res['Hs_heave'])} | {fmt(res['sigma_pitch_deg'])} | "
            f"{fmt(res['max_pitch_3h_deg'])} | {fmt(res['antenna_clearance_m'])} | "
            f"{res['verdict']} |",
            file=stream,
        )
    print("", file=stream)


def main():
    buf = io.StringIO()
    print("# SEA-IDOM Type-A — wave stability assessment (REV-B)\n", file=buf)
    print("Two configurations compared:\n", file=buf)
    print("- **(A) Literal REV-B proposal** — 3 m spar, 1.5 m freeboard, "
          "3rd ballast bottle on a 2 m rope at z = -3.5 m, water-filled "
          "around the hydrophone (~2.2 kg).", file=buf)
    print("- **(B) Recommended fix** — same hull, but hydrophone bottle "
          "pellet-ballasted to 5 kg AND a sealed 4 L surface flotation "
          "collar added at the SWL to compensate.\n", file=buf)

    report(TypeAGeometry(), "(A) Literal REV-B proposal", buf)
    report(TypeAGeometry.recommended_fix(), "(B) Recommended fix", buf)

    text = buf.getvalue()
    print(text)
    out = ROOT / "results" / "seaidom_typeA_stability.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


if __name__ == "__main__":
    main()
