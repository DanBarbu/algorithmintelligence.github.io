"""Frequency-domain RAOs + spectral stability assessment for SEA-IDOM Type-A.

Two RAO sources are supported:

1. Analytical small-body RAOs (always available) — used here when Capytaine
   is not installed. The buoy is small relative to the wavelengths of interest
   (kL << 1), so a damped-oscillator model captures the dominant physics:
       heave: vertical wave-following with added mass + radiation damping
       pitch: wave-slope forcing with a pendulum righting from submerged ballast
2. Capytaine BEM (use bem.solve_dataset) — drop-in replacement giving rigorous
   added mass / damping / excitation.

The spectral analysis is identical for either source.
"""

from dataclasses import dataclass
import numpy as np

from .geometry import TypeAGeometry
from .sea_states import SeaState, jonswap, spectral_moments, hs_from_spectrum


G = 9.81
RHO = 1025.0


@dataclass
class AnalyticalRAOs:
    """Damped-oscillator RAOs for a small spar-pendulum buoy."""
    geom: TypeAGeometry
    zeta_heave: float = 0.10        # heave damping ratio (radiation + viscous fins)
    zeta_pitch: float = 0.18        # pitch damping ratio (fins act as plates)

    def heave_natural_period(self) -> float:
        m_added = 1.5 * self.geom.total_mass      # ~50% added mass
        k_h = RHO * G * self.geom.waterplane_area
        return 2 * np.pi * np.sqrt(m_added / k_h)

    def pitch_natural_period(self) -> float:
        # moment of inertia about CG (kg m^2)
        g = self.geom
        ballast_m = g.n_ballast * g.ballast_mass
        r_ballast = abs(-g.spine_depth - g.vertical_cg)
        i_ballast = ballast_m * r_ballast ** 2
        r_spar = abs(-(g.spar_length / 2 - g.spar_freeboard) - g.vertical_cg)
        i_spar = g.m_spar * (g.spar_length ** 2 / 12 + r_spar ** 2)
        i_struct = (g.m_spine_struct + g.m_fins) * r_ballast ** 2
        i_top = (g.m_electronics_bottle + g.m_antenna_payload) * 0.1 ** 2
        i_total = i_ballast + i_spar + i_struct + i_top
        i_added = 1.5 * i_total
        gm_L, _ = g.gm()
        c_pitch = RHO * G * g.displaced_volume * gm_L
        return 2 * np.pi * np.sqrt(i_added / c_pitch)

    def heave_rao(self, omega: np.ndarray) -> np.ndarray:
        """|H_3(omega)| in m / m wave amplitude."""
        wn = 2 * np.pi / self.heave_natural_period()
        r = omega / wn
        return 1.0 / np.sqrt((1 - r ** 2) ** 2 + (2 * self.zeta_heave * r) ** 2)

    def pitch_rao(self, omega: np.ndarray) -> np.ndarray:
        """|H_5(omega)| in rad / m wave amplitude.

        Wave slope amplitude = k * A, k = omega^2 / g (deep water).
        Dynamic amplification factor about the pitch natural frequency.
        """
        wn = 2 * np.pi / self.pitch_natural_period()
        r = omega / wn
        k = omega ** 2 / G
        daf = 1.0 / np.sqrt((1 - r ** 2) ** 2 + (2 * self.zeta_pitch * r) ** 2)
        return k * daf


def spectral_response(
    omega: np.ndarray,
    rao: np.ndarray,
    s_eta: np.ndarray,
) -> dict:
    """Return spectral statistics of a response with RAO |H(omega)| and wave
    spectrum S_eta(omega).
    """
    s_resp = (rao ** 2) * s_eta
    m0 = spectral_moments(omega, s_resp, 0)
    m2 = spectral_moments(omega, s_resp, 2)
    sigma = np.sqrt(m0)
    # zero-crossing period
    tz = 2 * np.pi * np.sqrt(m0 / m2) if m2 > 0 else float("nan")
    # most-probable maximum in a 3-hour storm (Rayleigh): xm = sigma*sqrt(2*ln(N))
    # N = 3*3600 / Tz
    if tz > 0 and np.isfinite(tz):
        n_cycles = 3 * 3600.0 / tz
        x_max_3h = sigma * np.sqrt(2 * np.log(n_cycles))
    else:
        x_max_3h = float("nan")
    return {
        "sigma": sigma,
        "tz": tz,
        "hs_response": 4 * sigma,
        "x_max_3h": x_max_3h,
    }


def assess_sea_state(
    rao_model: AnalyticalRAOs,
    sea: SeaState,
    omega: np.ndarray | None = None,
) -> dict:
    if omega is None:
        omega = np.linspace(0.1, 6.0, 600)
    s_eta = jonswap(omega, sea.hs, sea.tp)
    h3 = rao_model.heave_rao(omega)
    h5 = rao_model.pitch_rao(omega)
    heave = spectral_response(omega, h3, s_eta)
    pitch = spectral_response(omega, h5, s_eta)

    pitch_sigma_deg = np.degrees(pitch["sigma"])
    pitch_max_deg = np.degrees(pitch["x_max_3h"])

    # antenna immersion / green-water risk: max vertical excursion at top of spar
    spar_top_above_swl = rao_model.geom.spar_freeboard
    vertical_excursion_3h = (
        heave["x_max_3h"]
        + np.tan(min(pitch["x_max_3h"], np.radians(60))) * spar_top_above_swl
    )

    # resonance proximity
    tp = sea.tp
    t5 = rao_model.pitch_natural_period()
    t3 = rao_model.heave_natural_period()
    resonance_pitch = abs(tp - t5) / t5
    resonance_heave = abs(tp - t3) / t3

    # stability verdict heuristics
    risks = []
    if pitch_max_deg > 30.0:
        risks.append("CAPSIZE")
    elif pitch_sigma_deg > 10.0:
        risks.append("Large heel")
    if resonance_pitch < 0.20:
        risks.append("Pitch resonance")
    if heave["hs_response"] > 1.2 * sea.hs:
        risks.append("Heave amplification")
    if vertical_excursion_3h > spar_top_above_swl + 0.2:
        risks.append("Antenna immersion")

    verdict = "OK" if not risks else " / ".join(risks)

    return {
        "sea_state": sea,
        "Hs_in": sea.hs,
        "Tp_in": sea.tp,
        "Hs_heave": heave["hs_response"],
        "sigma_heave_m": heave["sigma"],
        "max_heave_3h_m": heave["x_max_3h"],
        "sigma_pitch_deg": pitch_sigma_deg,
        "max_pitch_3h_deg": pitch_max_deg,
        "Tn_heave_s": t3,
        "Tn_pitch_s": t5,
        "antenna_clearance_m": spar_top_above_swl - vertical_excursion_3h,
        "verdict": verdict,
    }
