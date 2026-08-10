"""Capytaine BEM driver for the SEA-IDOM Type-A buoy.

Run this once Capytaine is installed in the environment:

    pip install capytaine xarray netcdf4 matplotlib
    python -m seaidom.bem

It builds the body, sweeps frequency for radiation + diffraction problems, and
writes the hydro dataset to results/seaidom_typeA.nc (Nemoh/BEMIO-compatible
so it can be reused by WEC-Sim / Moordyn for time-domain follow-up).
"""

from pathlib import Path
import numpy as np

from .geometry import TypeAGeometry, build_capytaine_body


def solve_dataset(
    omegas=None,
    wave_directions=(0.0,),
    out_path: str | Path = "results/seaidom_typeA.nc",
):
    import capytaine as cpt

    if omegas is None:
        omegas = np.linspace(0.2, 4.0, 40)

    geom = TypeAGeometry()
    body = build_capytaine_body(geom)

    problems = []
    for w in omegas:
        for dof in body.dofs:
            problems.append(cpt.RadiationProblem(body=body, omega=w, radiating_dof=dof))
        for beta in wave_directions:
            problems.append(cpt.DiffractionProblem(body=body, omega=w, wave_direction=beta))

    solver = cpt.BEMSolver()
    results = solver.solve_all(problems, n_jobs=-1)
    dataset = cpt.assemble_dataset(results)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_netcdf(out)
    return dataset


if __name__ == "__main__":
    ds = solve_dataset()
    print(ds)
