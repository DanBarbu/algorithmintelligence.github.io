"""Run the analytical spectral stability sweep for SEA-IDOM Type-A.

Prints a markdown summary table to stdout and writes results/seaidom_typeA_stability.md.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from seaidom.geometry import TypeAGeometry  # noqa: E402
from seaidom.sea_states import SEA_STATES   # noqa: E402
from seaidom.stability import AnalyticalRAOs, assess_sea_state  # noqa: E402


def fmt(x, d=2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or not np.isfinite(x))):
        return "—"
    return f"{x:.{d}f}"


def main():
    g = TypeAGeometry()
    rao = AnalyticalRAOs(g)

    print("# SEA-IDOM Type-A — wave stability assessment\n")
    print("## Static configuration\n")
    gm_L, gm_T = g.gm()
    print(f"- Total mass: **{g.total_mass:.2f} kg**")
    print(f"- Displaced volume: **{g.displaced_volume*1e3:.2f} L** "
          f"(net buoyancy {g.displaced_volume*1025 - g.total_mass:+.2f} kg)")
    print(f"- Waterplane area A_wp: **{g.waterplane_area*1e4:.1f} cm²**")
    print(f"- Vertical CG (z): **{g.vertical_cg:+.3f} m**")
    print(f"- Vertical CB (z): **{g.vertical_cb:+.3f} m**")
    print(f"- BG (CG above CB): **{g.vertical_cg - g.vertical_cb:+.3f} m**")
    print(f"- Effective GM (pitch / roll): **{gm_L:.2f} / {gm_T:.2f} m**")
    print(f"- Heave natural period T₃: **{rao.heave_natural_period():.2f} s**")
    print(f"- Pitch natural period T₅: **{rao.pitch_natural_period():.2f} s**\n")

    print("## Per–sea-state response (3-hour stationary storm, JONSWAP γ=3.3)\n")
    header = ("| Sea state | Hs (m) | Tp (s) | "
              "Hs heave (m) | σ pitch (°) | max pitch 3h (°) | "
              "antenna clearance (m) | verdict |")
    sep = "|---|---:|---:|---:|---:|---:|---:|---|"
    print(header)
    print(sep)

    rows = []
    for sea in SEA_STATES:
        res = assess_sea_state(rao, sea)
        rows.append(res)
        print(
            f"| {sea.code} {sea.description} | {sea.hs:.2f} | {sea.tp:.1f} | "
            f"{fmt(res['Hs_heave'])} | {fmt(res['sigma_pitch_deg'])} | "
            f"{fmt(res['max_pitch_3h_deg'])} | {fmt(res['antenna_clearance_m'])} | "
            f"{res['verdict']} |"
        )

    out = ROOT / "results" / "seaidom_typeA_stability.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    # write the same content to the file
    import io
    buf = io.StringIO()
    sys_stdout = sys.stdout
    sys.stdout = buf
    try:
        # re-run for file
        print("# SEA-IDOM Type-A — wave stability assessment\n")
        print(f"- Total mass: {g.total_mass:.2f} kg")
        print(f"- Displaced volume: {g.displaced_volume*1e3:.2f} L")
        print(f"- A_wp: {g.waterplane_area*1e4:.1f} cm²")
        print(f"- CG: {g.vertical_cg:+.3f} m  |  CB: {g.vertical_cb:+.3f} m")
        print(f"- GM_L / GM_T: {gm_L:.2f} / {gm_T:.2f} m")
        print(f"- Tn_heave: {rao.heave_natural_period():.2f} s  |  "
              f"Tn_pitch: {rao.pitch_natural_period():.2f} s\n")
        print(header)
        print(sep)
        for sea, res in zip(SEA_STATES, rows):
            print(
                f"| {sea.code} {sea.description} | {sea.hs:.2f} | {sea.tp:.1f} | "
                f"{fmt(res['Hs_heave'])} | {fmt(res['sigma_pitch_deg'])} | "
                f"{fmt(res['max_pitch_3h_deg'])} | {fmt(res['antenna_clearance_m'])} | "
                f"{res['verdict']} |"
            )
    finally:
        sys.stdout = sys_stdout
    out.write_text(buf.getvalue())


if __name__ == "__main__":
    main()
