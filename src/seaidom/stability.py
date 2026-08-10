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
        """Pitch natural period (s). Returns NaN if GM <= 0 (statically unstable)."""
        g = self.geom
        ballast_m = g.n_ballast * g.ballast_mass
        r_ballast = abs(-g.spine_depth - g.vertical_cg)
        i_ballast = ballast_m * r_ballast ** 2
        r_spar = abs(-(g.spar_length / 2 - g.spar_freeboard) - g.vertical_cg)
        i_spar = g.m_spar * (g.spar_length ** 2 / 12 + r_spar ** 2)
        i_struct = (g.m_spine_struct + g.m_fins) * r_ballast ** 2
        i_top = (g.m_electronics_bottle + g.m_antenna_payload) * 0.1 ** 2
        # Hydrophone bottle on a 2 m rope: rope-pendulum period is
        #   T_rope = 2 pi sqrt(L_rope/g) ≈ 2.84 s.
        # For wave periods >> T_rope the bottle hangs plumb beneath the spar tip
        # and only contributes its NET weight to the spar tip — its swinging
        # inertia is decoupled from body pitch. For wave periods < T_rope it is
        # nearly inertial-fixed and rigidly coupled. We model the typical regime
        # (Tp 5-12 s, rope ~3 s) as slow: rigid coupling, but only the net
        # (mass - displaced) inertia contributes.
        net_hydro = max(g.hydrophone_bottle_mass - RHO * g.hydrophone_bottle_volume, 0.0)
        r_hydro = abs(g.hydrophone_bottle_z - g.vertical_cg)
        i_hydro = net_hydro * r_hydro ** 2
        i_total = i_ballast + i_spar + i_struct + i_top + i_hydro
        i_added = 1.5 * i_total
        gm_L, _ = g.gm()
        if gm_L <= 0:
            return float("nan")     # statically unstable in pitch
        c_pitch = RHO * G * g.displaced_volume * gm_L
        return 2 * np.pi * np.sqrt(i_added / c_pitch)

    def heave_rao_complex(self, omega: np.ndarray) -> np.ndarray:
        """Complex heave RAO (m/m), 2nd-order damped oscillator.

        H_3(0) = 1 (perfect long-wave following), H_3(inf) -> 0 (no following).
        """
        wn = 2 * np.pi / self.heave_natural_period()
        denom = wn ** 2 - omega ** 2 + 2j * self.zeta_heave * wn * omega
        return wn ** 2 / denom

    def heave_rao(self, omega: np.ndarray) -> np.ndarray:
        """|H_3(omega)| in m / m wave amplitude."""
        return np.abs(self.heave_rao_complex(omega))

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


def antenna_immersion_analysis(
    rao_model: AnalyticalRAOs,
    sea: SeaState,
    omega: np.ndarray | None = None,
    storm_duration_s: float = 3 * 3600.0,
    survivable_duration_s: float = 60.0,
) -> dict:
    """Stationary Gaussian level-crossing analysis of antenna immersion.

    The antenna is "wet" when its world-frame z falls below the local wave
    surface. For a surface-piercing spar this is governed by the relative
    motion  Y(t) = eta(t) - heave(t)  crossing the freeboard threshold h_fb
    (with a small second-order pitch correction).

    Returns: instantaneous wet probability, mean immersion duration per event,
    expected number of events per storm, and the probability that any single
    event exceeds `survivable_duration_s`.
    """
    if omega is None:
        omega = np.linspace(0.05, 12.0, 1200)

    g = rao_model.geom
    h_fb = g.spar_freeboard

    # JONSWAP wave spectrum
    s_eta = jonswap(omega, sea.hs, sea.tp)

    # Complex heave RAO -> relative-motion spectrum  |1 - H_3|^2 * S_eta
    h3 = rao_model.heave_rao_complex(omega)
    rel_factor = np.abs(1.0 - h3) ** 2
    s_y = rel_factor * s_eta

    m0_y = float(np.trapezoid(s_y, omega))
    m2_y = float(np.trapezoid(s_y * omega ** 2, omega))
    sigma_y = np.sqrt(m0_y) if m0_y > 0 else 0.0

    # Effective freeboard threshold reduced by mean pitch-induced drop
    s_theta = (rao_model.pitch_rao(omega) ** 2) * s_eta
    sigma_theta = np.sqrt(np.trapezoid(s_theta, omega)) if rao_model.geom.is_statically_stable else 0.0
    pitch_drop = h_fb * (sigma_theta ** 2) / 2.0   # E[h_fb * theta^2 / 2]
    threshold = max(h_fb - pitch_drop, 0.0)

    if sigma_y <= 0 or threshold <= 0:
        # numerical degenerate
        return {
            "sigma_y_m": sigma_y,
            "effective_threshold_m": threshold,
            "sigma_pitch_deg": np.degrees(sigma_theta),
            "p_wet_instant": 0.0,
            "rate_events_per_hour": 0.0,
            "mean_event_duration_s": 0.0,
            "n_events_per_storm": 0.0,
            "p_event_exceeds_survivable": 0.0,
            "survivable": True,
        }

    # zero-up-crossing rate of Y(t)
    nu0 = (1.0 / (2 * np.pi)) * np.sqrt(m2_y / m0_y)
    # Rice formula: rate of up-crossings of level a by Gaussian Y
    a = threshold
    z = a / sigma_y
    nu_a = nu0 * np.exp(-0.5 * z ** 2)
    # Instantaneous P(Y > a) for zero-mean Gaussian
    from math import erfc
    p_wet = 0.5 * erfc(z / np.sqrt(2))
    # Mean duration of an excursion above a (P / rate)
    tau = p_wet / nu_a if nu_a > 0 else float("inf")
    # Expected number of events in storm
    n_events = nu_a * storm_duration_s
    # Excursion durations for narrow-band Gaussian above a high level
    # are well approximated by an exponential distribution with mean tau.
    # => P(any single event > T) = exp(-T/tau).
    p_long = float(np.exp(-survivable_duration_s / tau)) if tau > 0 else 0.0
    # Probability at least one event in the storm exceeds T (Poisson approx.):
    p_storm_violation = 1.0 - np.exp(-n_events * p_long)

    return {
        "sigma_y_m": sigma_y,
        "effective_threshold_m": threshold,
        "sigma_pitch_deg": float(np.degrees(sigma_theta)),
        "p_wet_instant": float(p_wet),
        "rate_events_per_hour": float(nu_a * 3600.0),
        "mean_event_duration_s": float(tau),
        "n_events_per_storm": float(n_events),
        "p_event_exceeds_survivable": float(p_long),
        "p_storm_violation": float(p_storm_violation),
        "survivable": p_storm_violation < 0.01,   # < 1% chance of >60 s wetting per 3-h storm
    }


def assess_sea_state(
    rao_model: AnalyticalRAOs,
    sea: SeaState,
    omega: np.ndarray | None = None,
) -> dict:
    if not rao_model.geom.is_statically_stable:
        return {
            "sea_state": sea,
            "Hs_in": sea.hs,
            "Tp_in": sea.tp,
            "Hs_heave": float("nan"),
            "sigma_heave_m": float("nan"),
            "max_heave_3h_m": float("nan"),
            "sigma_pitch_deg": float("nan"),
            "max_pitch_3h_deg": float("nan"),
            "Tn_heave_s": rao_model.heave_natural_period(),
            "Tn_pitch_s": float("nan"),
            "antenna_clearance_m": float("nan"),
            "verdict": "STATICALLY UNSTABLE — capsizes at rest",
        }
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
