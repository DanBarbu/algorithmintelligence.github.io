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

    # Vertical spar (rigid pole) — REV 2026-06b
    spar_length: float = 3.00               # m, total
    spar_freeboard: float = 1.50            # m, above SWL  (=> 1.50 m submerged)
    spar_diameter: float = 0.030            # m

    # Submerged spine (horizontal bar) — attached at spar tip
    spine_length: float = 1.20              # m
    spine_diameter: float = 0.025           # m
    spine_depth: float = 1.50               # m below SWL  (= spar tip)

    # 6 locked PET-plate damping fins on the spine
    n_fins: int = 6
    fin_length: float = 0.20                # m (flattened bottle major)
    fin_width: float = 0.08                 # m (flattened bottle minor)
    fin_thickness: float = 0.004            # m

    # 2 water-filled ballast bottles strapped under spine
    n_ballast: int = 2
    ballast_volume: float = 2.0e-3          # m^3 each
    ballast_mass: float = 2.0               # kg each (water fill)

    # 3rd ballast bottle — hydrophone housing, rope-tethered below spar tip.
    # Literal SEA-IDOM family spec: PET bottle water-filled around the sensor.
    # Net buoyancy is near-neutral. See stability report for the static-stability
    # implications and the recommended pellet-ballast upgrade.
    hydrophone_bottle_volume: float = 2.0e-3        # m^3
    hydrophone_bottle_mass: float = 2.2             # kg  (hydrophone + water fill)
    hydrophone_rope_length: float = 2.00            # m  rope from spar tip
    hydrophone_rope_diameter: float = 0.004         # m  (negligible hydro)

    # Mass budget (kg)
    m_electronics_bottle: float = 0.7       # bottle + electronics + solar
    m_antenna_payload: float = 0.3
    m_spar: float = 2.0                     # HDPE 30 mm OD x 3.0 m
    m_spine_struct: float = 0.5             # spine + connectors
    m_fins: float = 0.2                     # 6 PET plates + connectors

    # Supplementary surface flotation collar (sealed). Zero in the literal
    # SEA-IDOM family spec; non-zero in the recommended_fix() configuration
    # to compensate for the pellet-ballasted hydrophone bottle.
    surface_collar_volume: float = 0.0      # m^3
    surface_collar_mass: float = 0.0        # kg
    surface_collar_diameter: float = 0.20   # m  (only used when collar > 0)

    # Mooring (Type-A: single-point at spine center)
    mooring_attachment_z: float = -1.50     # at spar tip / spine depth
    mooring_stiffness_h: float = 50.0       # N/m (compliant surge restraint)

    @classmethod
    def recommended_fix(cls) -> "TypeAGeometry":
        """Geometry with the minimum modifications needed to make the REV-B
        proposal both statically stable AND floating:

        1. Pellet-ballast the hydrophone bottle to ~5 kg total
           (hydrophone + water + ~3 kg lead/steel shot or sand).
        2. Add a sealed 4 L surface flotation collar at the SWL to compensate
           for the extra ballast mass (without it the buoy would sink).
        """
        return cls(
            hydrophone_bottle_mass=5.0,
            surface_collar_volume=4.0e-3,
            surface_collar_mass=0.5,
        )

    @property
    def hydrophone_bottle_z(self) -> float:
        """Depth of the rope-tethered hydrophone bottle CG (m, negative = below SWL)."""
        return -(self.spine_depth + self.hydrophone_rope_length)

    @property
    def total_mass(self) -> float:
        return (
            self.m_electronics_bottle
            + self.m_antenna_payload
            + self.m_spar
            + self.m_spine_struct
            + self.m_fins
            + self.n_ballast * self.ballast_mass
            + self.hydrophone_bottle_mass
            + self.surface_collar_mass
        )

    @property
    def displaced_volume(self) -> float:
        """Submerged volume at static equilibrium (m^3)."""
        v_ballast = self.n_ballast * self.ballast_volume
        v_spine = 3.1416 * (self.spine_diameter / 2) ** 2 * self.spine_length
        spar_sub = self.spar_length - self.spar_freeboard
        v_spar = 3.1416 * (self.spar_diameter / 2) ** 2 * spar_sub
        v_bot = 0.5 * self.bottle_volume
        v_hydro = self.hydrophone_bottle_volume
        # collar half-submerged at SWL
        v_collar = 0.5 * self.surface_collar_volume
        return v_ballast + v_spine + v_spar + v_bot + v_hydro + v_collar

    @property
    def waterplane_area(self) -> float:
        """A_wp at SWL (m^2): horizontal bottle slice + spar pierce + collar."""
        a_bottle = self.bottle_length * self.bottle_diameter
        a_spar = 3.1416 * (self.spar_diameter / 2) ** 2
        if self.surface_collar_volume > 0:
            a_collar = 3.1416 * (self.surface_collar_diameter / 2) ** 2
        else:
            a_collar = 0.0
        return a_bottle + a_spar + a_collar

    @property
    def vertical_cg(self) -> float:
        """CG above SWL (m). Negative = below SWL."""
        ballast_m = self.n_ballast * self.ballast_mass
        m_lower = ballast_m + self.m_spine_struct + self.m_fins
        z_lower = -self.spine_depth
        m_spar = self.m_spar
        # spar CG: midpoint of full 3 m bar, measured from SWL
        z_spar = -(self.spar_length / 2 - self.spar_freeboard)
        m_upper = self.m_electronics_bottle + self.m_antenna_payload
        z_upper = +0.10                 # bottle CG ~ at WL, antenna +0.4
        m_hydro = self.hydrophone_bottle_mass
        z_hydro = self.hydrophone_bottle_z
        m_collar = self.surface_collar_mass
        z_collar = 0.0
        num = (
            m_lower * z_lower
            + m_spar * z_spar
            + m_upper * z_upper
            + m_hydro * z_hydro
            + m_collar * z_collar
        )
        return num / self.total_mass

    @property
    def vertical_cb(self) -> float:
        """CB below SWL of submerged volume (m)."""
        v_ballast = self.n_ballast * self.ballast_volume
        z_ballast = -self.spine_depth
        v_spar = 3.1416 * (self.spar_diameter / 2) ** 2 * (
            self.spar_length - self.spar_freeboard
        )
        z_spar = -(self.spar_length - self.spar_freeboard) / 2
        v_bot = 0.5 * self.bottle_volume
        z_bot = -0.5 * self.bottle_diameter / 2
        v_hydro = self.hydrophone_bottle_volume
        z_hydro = self.hydrophone_bottle_z
        v_collar = 0.5 * self.surface_collar_volume
        z_collar = -0.25 * self.surface_collar_diameter
        v_total = self.displaced_volume
        return (
            z_ballast * v_ballast
            + z_spar * v_spar
            + z_bot * v_bot
            + z_hydro * v_hydro
            + v_collar * z_collar
        ) / v_total

    def gm(self, rho: float = 1025.0) -> tuple[float, float]:
        """Metacentric heights GM_L (pitch) and GM_T (roll), in metres.

        Standard naval-architecture formula GM = z_B + BM - z_G, where z is
        positive up with origin at SWL. Negative GM => statically unstable.
        """
        b = self.bottle_diameter
        L = self.bottle_length
        I_T = L * b ** 3 / 12.0           # transverse waterplane second moment
        I_L = b * L ** 3 / 12.0           # longitudinal
        bm_T = I_T / self.displaced_volume
        bm_L = I_L / self.displaced_volume
        gm_L = self.vertical_cb + bm_L - self.vertical_cg
        gm_T = self.vertical_cb + bm_T - self.vertical_cg
        return gm_L, gm_T

    @property
    def is_statically_stable(self) -> bool:
        gm_L, gm_T = self.gm()
        return gm_L > 0 and gm_T > 0


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

    # hydrophone bottle (rope-tethered below spar tip)
    hydro_bottle = cpt.meshes.predefined.mesh_horizontal_cylinder(
        length=geom.bottle_length,
        radius=geom.bottle_diameter / 2,
        center=(0.0, 0.0, geom.hydrophone_bottle_z),
        resolution=(6, 20, 4),
    )

    mesh = bottle + spar + spine + ballasts[0] + ballasts[1] + hydro_bottle
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
