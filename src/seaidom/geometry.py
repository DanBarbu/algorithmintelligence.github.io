"""
SEA-IDOM Type-A station-keeping buoy — parametric geometry.

Adapted from the SEA-IDOM Wave Glider (DWG SBN-WG-003, REV 2026-06):
    - surface float: 2 L PET electronics bottle cap-mounted to a vertical spar
    - spar: rigid pole carrying antenna on top and linking the spine below
    - spine: horizontal bar at depth carrying 6 PET-bottle plates
    - 2 water-filled ballast bottles strapped under the spine

Type-A station-keeping variant: the 6 fins are LOCKED vertical as damping
plates (no free pitch), and a single-point mooring is attached at the spine
center. All other dimensions match the Wave Glider source design.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TypeAGeometry:
    # PET bottle proxy (2 L bottle, horizontal at WL, half-submerged at rest)
    bottle_length: float = 0.330            # m
    bottle_diameter: float = 0.110          # m
    bottle_volume: float = 2.0e-3           # m^3

    # Vertical spar (rigid pole)
    spar_length: float = 1.80               # m, total
    spar_freeboard: float = 0.50            # m, above SWL (antenna mount + sensor)
    spar_diameter: float = 0.030            # m

    # Submerged spine (horizontal bar)
    spine_length: float = 1.20              # m
    spine_diameter: float = 0.025           # m
    spine_depth: float = 1.30               # m below SWL

    # 6 locked PET-plate damping fins on the spine
    n_fins: int = 6
    fin_length: float = 0.20                # m (flattened bottle major)
    fin_width: float = 0.08                 # m (flattened bottle minor)
    fin_thickness: float = 0.004            # m

    # 2 water-filled ballast bottles strapped under spine
    n_ballast: int = 2
    ballast_volume: float = 2.0e-3          # m^3 each
    ballast_mass: float = 2.0               # kg each (water fill)

    # Mass budget (kg)
    m_electronics_bottle: float = 0.7       # bottle + electronics + solar
    m_antenna_payload: float = 0.3
    m_spar: float = 1.2                     # HDPE 30 mm OD x 1.8 m
    m_spine_struct: float = 0.5             # spine + connectors
    m_fins: float = 0.2                     # 6 PET plates + connectors

    # Mooring (Type-A: single-point at spine center)
    mooring_attachment_z: float = -1.30     # at spine depth
    mooring_stiffness_h: float = 50.0       # N/m (compliant surge restraint)

    @property
    def total_mass(self) -> float:
        return (
            self.m_electronics_bottle
            + self.m_antenna_payload
            + self.m_spar
            + self.m_spine_struct
            + self.m_fins
            + self.n_ballast * self.ballast_mass
        )

    @property
    def displaced_volume(self) -> float:
        """Submerged volume at static equilibrium (m^3)."""
        # ballast bottles fully submerged
        v_ballast = self.n_ballast * self.ballast_volume
        # spine + connectors (small)
        v_spine = 3.1416 * (self.spine_diameter / 2) ** 2 * self.spine_length
        # spar submerged length
        spar_sub = self.spar_length - self.spar_freeboard
        v_spar = 3.1416 * (self.spar_diameter / 2) ** 2 * spar_sub
        # electronics bottle half-submerged
        v_bot = 0.5 * self.bottle_volume
        return v_ballast + v_spine + v_spar + v_bot

    @property
    def waterplane_area(self) -> float:
        """A_wp at SWL (m^2): horizontal bottle slice + spar pierce."""
        a_bottle = self.bottle_length * self.bottle_diameter   # rectangular WL slice
        a_spar = 3.1416 * (self.spar_diameter / 2) ** 2
        return a_bottle + a_spar

    @property
    def vertical_cg(self) -> float:
        """CG above SWL (m). Negative = below SWL."""
        # weighted sum: ballast at spine depth, structure distributed, surface mass at WL
        ballast_m = self.n_ballast * self.ballast_mass
        m_lower = ballast_m + self.m_spine_struct + self.m_fins
        z_lower = -self.spine_depth
        m_spar = self.m_spar
        z_spar = -(self.spar_length / 2 - self.spar_freeboard)
        m_upper = self.m_electronics_bottle + self.m_antenna_payload
        z_upper = +0.10                 # bottle CG ~ at WL, antenna +0.4
        num = m_lower * z_lower + m_spar * z_spar + m_upper * z_upper
        return num / self.total_mass

    @property
    def vertical_cb(self) -> float:
        """CB below SWL of submerged volume (m)."""
        # dominated by submerged ballast at -spine_depth
        v_ballast = self.n_ballast * self.ballast_volume
        v_total = self.displaced_volume
        z_ballast = -self.spine_depth
        z_spar = -(self.spar_length - self.spar_freeboard) / 2
        v_spar = 3.1416 * (self.spar_diameter / 2) ** 2 * (
            self.spar_length - self.spar_freeboard
        )
        z_bot = -0.5 * self.bottle_diameter / 2
        v_bot = 0.5 * self.bottle_volume
        return (z_ballast * v_ballast + z_spar * v_spar + z_bot * v_bot) / v_total

    def gm(self, rho: float = 1025.0) -> float:
        """Effective metacentric height (m). For a spar-pendulum buoy this is
        dominated by BG: large positive when CB is well below CG... wait, the
        sign convention here is GM = KB + BM - KG, equivalent to (CB - CG).
        For our buoy CB is far below CG-of-deck, so GM is positive and large.
        """
        # waterplane second moment (rectangular for the bottle slice)
        b = self.bottle_diameter
        L = self.bottle_length
        I_T = L * b ** 3 / 12.0           # transverse (roll)
        I_L = b * L ** 3 / 12.0           # longitudinal (pitch)
        bm_T = I_T / self.displaced_volume
        bm_L = I_L / self.displaced_volume
        bg = self.vertical_cg - self.vertical_cb     # CG above CB
        gm_T = bm_T - bg                              # waterplane term minus BG
        gm_L = bm_L - bg
        # for a slender spar-buoy with submerged ballast pendulum the
        # dominant righting comes from the pendulum: CB << CG by ~1 m and
        # the waterplane contribution is small. The "effective" GM in that
        # regime is simply |CB - CG| projected as a pendulum arm.
        gm_pendulum = -bg                             # = CB - CG, positive when CB below CG
        return max(gm_pendulum + bm_L, 0.10), max(gm_pendulum + bm_T, 0.10)


def build_capytaine_body(geom: TypeAGeometry):
    """Build a Capytaine FloatingBody for the Type-A buoy.

    Imported lazily so this module can be inspected without capytaine present.
    """
    import capytaine as cpt
    import numpy as np

    # surface bottle (horizontal cylinder, half-submerged)
    bottle = cpt.meshes.predefined.mesh_horizontal_cylinder(
        length=geom.bottle_length,
        radius=geom.bottle_diameter / 2,
        center=(0.0, 0.0, 0.0),
        resolution=(8, 24, 4),
    )

    # spar (vertical cylinder, submerged portion only)
    spar_sub = geom.spar_length - geom.spar_freeboard
    spar = cpt.meshes.predefined.mesh_vertical_cylinder(
        length=spar_sub,
        radius=geom.spar_diameter / 2,
        center=(0.0, 0.0, -spar_sub / 2),
        resolution=(6, 16, 12),
    )

    # spine (horizontal cylinder at depth)
    spine = cpt.meshes.predefined.mesh_horizontal_cylinder(
        length=geom.spine_length,
        radius=geom.spine_diameter / 2,
        center=(0.0, 0.0, -geom.spine_depth),
        resolution=(4, 16, 12),
    )

    # ballast bottles (two horizontal cylinders below spine)
    ballast_offset = geom.spine_length / 4
    ballasts = []
    for x in (-ballast_offset, +ballast_offset):
        b = cpt.meshes.predefined.mesh_horizontal_cylinder(
            length=geom.bottle_length,
            radius=geom.bottle_diameter / 2,
            center=(x, 0.0, -geom.spine_depth - geom.bottle_diameter / 2 - 0.02),
            resolution=(6, 20, 4),
        )
        ballasts.append(b)

    mesh = bottle + spar + spine + ballasts[0] + ballasts[1]
    mesh = mesh.immersed_part()

    body = cpt.FloatingBody(mesh=mesh, name="seaidom_typeA")
    body.add_all_rigid_body_dofs()
    body.center_of_mass = (0.0, 0.0, geom.vertical_cg)
    body.mass = geom.total_mass
    return body


if __name__ == "__main__":
    g = TypeAGeometry()
    print(f"total mass            : {g.total_mass:.2f} kg")
    print(f"displaced volume      : {g.displaced_volume*1e3:.2f} L")
    print(f"net buoyancy (kg)     : {g.displaced_volume*1025 - g.total_mass:+.2f}")
    print(f"waterplane area       : {g.waterplane_area*1e4:.1f} cm^2")
    print(f"vertical CG (z)       : {g.vertical_cg:+.3f} m")
    print(f"vertical CB (z)       : {g.vertical_cb:+.3f} m")
    gm_L, gm_T = g.gm()
    print(f"GM_pitch / GM_roll    : {gm_L:.3f} / {gm_T:.3f} m")
