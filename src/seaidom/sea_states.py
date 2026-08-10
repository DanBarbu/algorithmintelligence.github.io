"""WMO sea state matrix + JONSWAP / Pierson-Moskowitz wave spectra."""

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class SeaState:
    code: str
    description: str
    hs: float            # significant wave height (m)
    tp: float            # peak period (s)


# WMO sea-state table (representative central values).
SEA_STATES = [
    SeaState("SS2", "Smooth",        0.30, 5.0),
    SeaState("SS3", "Slight",        0.90, 6.5),
    SeaState("SS4", "Moderate",      1.90, 8.0),
    SeaState("SS5", "Rough",         3.30, 10.0),
    SeaState("SS6", "Very Rough",    5.00, 12.0),
]


def jonswap(omega: np.ndarray, hs: float, tp: float, gamma: float = 3.3) -> np.ndarray:
    """One-sided JONSWAP spectrum S(omega) in m^2 s/rad.

    gamma = 1.0 -> Pierson-Moskowitz; 3.3 is the open-ocean default.
    """
    omega = np.asarray(omega, dtype=float)
    wp = 2 * np.pi / tp
    sigma = np.where(omega <= wp, 0.07, 0.09)
    # base PM
    pm = (5.0 / 16.0) * hs ** 2 * wp ** 4 / omega ** 5 * np.exp(-1.25 * (wp / omega) ** 4)
    # peak-enhancement
    r = np.exp(-((omega - wp) ** 2) / (2 * sigma ** 2 * wp ** 2))
    a_gamma = 1.0 - 0.287 * np.log(gamma)        # normalisation so m0 matches Hs
    s = a_gamma * pm * gamma ** r
    s[omega <= 0] = 0.0
    return s


def spectral_moments(omega: np.ndarray, s: np.ndarray, order: int = 0) -> float:
    return float(np.trapezoid(s * omega ** order, omega))


def hs_from_spectrum(omega: np.ndarray, s: np.ndarray) -> float:
    return 4.0 * np.sqrt(spectral_moments(omega, s, 0))
