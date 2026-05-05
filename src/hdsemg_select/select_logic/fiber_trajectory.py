from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import correlate
from scipy.stats import linregress


@dataclass
class FiberTrajectoryResult:
    fiber_angle_deg: float
    conduction_velocity_ms: float
    iz_position_m: float | None
    r_squared: float
    search_angles: np.ndarray
    search_r2: np.ndarray
    pairwise_delays_ms: np.ndarray   # signed adjacent-bin delays at θ_best
    pairwise_distances_m: np.ndarray  # bin midpoint positions at θ_best


class FiberTrajectoryAnalyzer:
    """Estimate muscle fiber trajectory from a 2D HD-sEMG electrode array.

    Angle search: anchor-first cross-correlation + delay plane fitting.
    IZ detection: adjacent projection-bin sign reversal.

    Reference: Farina & Merletti, J Neurosci Methods 134:199-208, 2004.
               https://pubmed.ncbi.nlm.nih.gov/15003386/
    """

    _MIN_CV_MS = 2.0        # physiological lower bound (m/s); typical range 2–6 m/s
    _MAX_CV_MS = 10.0       # physiological upper bound (m/s)
    _MIN_VALID_PAIRS = 4    # fewer valid pairs → regression is unreliable

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        signals: np.ndarray,
        grid,
        display_grid: np.ndarray,
        fs: float,
    ) -> FiberTrajectoryResult:
        """Run full fiber trajectory analysis.

        Parameters
        ----------
        signals:      (n_samples, n_channels) monopolar EMG, float32/64
        grid:         object with .rows, .cols, .ied_mm, .emg_indices
        display_grid: (rows, cols) array of local electrode indices; NaN = empty
        fs:           sampling rate in Hz
        """
        rows, cols = display_grid.shape
        if rows < 2 and cols < 2:
            raise ValueError(
                f"Grid too small for propagation analysis ({rows}×{cols}); "
                "need at least 2 electrodes in one direction."
            )

        ied_m = grid.ied_mm * 1e-3
        mono = self._prepare_signals(signals, grid, display_grid)

        angles = np.arange(-90, 91, dtype=float)
        r2_per_angle = np.zeros(len(angles))
        cv_per_angle = np.zeros(len(angles))

        for i, theta in enumerate(angles):
            cv, r2 = self._fit_at_angle(theta, mono, ied_m, fs)
            cv_per_angle[i] = cv
            r2_per_angle[i] = r2

        best_idx = int(np.argmax(r2_per_angle))
        best_angle = float(angles[best_idx])
        best_cv = float(cv_per_angle[best_idx])
        best_r2 = float(r2_per_angle[best_idx])

        adj_delays_ms, adj_positions_m = self._binned_adj_delays(
            best_angle, mono, ied_m, fs
        )
        iz_pos = self._detect_iz(adj_delays_ms, adj_positions_m)

        return FiberTrajectoryResult(
            fiber_angle_deg=best_angle,
            conduction_velocity_ms=best_cv,
            iz_position_m=iz_pos,
            r_squared=best_r2,
            search_angles=angles,
            search_r2=r2_per_angle,
            pairwise_delays_ms=adj_delays_ms,
            pairwise_distances_m=adj_positions_m,
        )

    def detect_iz_at_angle(
        self,
        signals: np.ndarray,
        grid,
        display_grid: np.ndarray,
        fs: float,
        angle_deg: float,
    ) -> float | None:
        """Detect innervation zone at a known fiber angle.

        Useful when the angle is known from anatomy or a prior analysis step.
        Returns the projected position (m) of the IZ, or None if not found.
        """
        ied_m = grid.ied_mm * 1e-3
        mono = self._prepare_signals(signals, grid, display_grid)
        adj_delays_ms, adj_positions_m = self._binned_adj_delays(
            angle_deg, mono, ied_m, fs
        )
        return self._detect_iz(adj_delays_ms, adj_positions_m)

    # ------------------------------------------------------------------
    # Signal preparation
    # ------------------------------------------------------------------

    def _prepare_signals(
        self,
        signals: np.ndarray,
        grid,
        display_grid: np.ndarray,
    ) -> dict[tuple[int, int], np.ndarray]:
        """Return monopolar signals keyed by (row, col) grid position.

        display_grid cells contain LOCAL electrode indices (0…n_electrodes-1).
        emg_indices maps local → global channel index in the signals array.
        """
        rows, cols = display_grid.shape
        emg_indices = grid.emg_indices
        mono: dict[tuple[int, int], np.ndarray] = {}
        for r in range(rows):
            for c in range(cols):
                cell = display_grid[r, c]
                if np.isnan(cell):
                    continue
                local_electrode_idx = int(cell)         # 0 … n_electrodes-1
                if local_electrode_idx >= len(emg_indices):
                    continue
                global_ch_idx = emg_indices[local_electrode_idx]  # column in signals
                if global_ch_idx >= signals.shape[1]:
                    continue
                mono[(r, c)] = signals[:, global_ch_idx].astype(np.float64)
        return mono

    # ------------------------------------------------------------------
    # Angle search — anchor-first regression
    # ------------------------------------------------------------------

    def _anchor_pairs(
        self,
        theta_deg: float,
        mono: dict[tuple[int, int], np.ndarray],
        ied_m: float,
    ) -> list[tuple[tuple[int, int], tuple[int, int], float]]:
        """Pair every electrode with the minimum-projection anchor.

        Produces N-1 pairs with monotonically increasing distances, ensuring
        the regression always has varying x values regardless of fiber angle.
        """
        theta = np.radians(theta_deg)
        proj: list[tuple[float, tuple[int, int]]] = []
        for r, c in mono:
            p = (r * np.sin(theta) + c * np.cos(theta)) * ied_m
            proj.append((p, (r, c)))
        proj.sort(key=lambda x: x[0])

        if len(proj) < 2:
            return []

        p_0, pos_0 = proj[0]
        pairs = []
        for k in range(1, len(proj)):
            p_k, pos_k = proj[k]
            dist = p_k - p_0
            if dist > 1e-9:
                pairs.append((pos_0, pos_k, dist))
        return pairs

    def _fit_at_angle(
        self,
        theta_deg: float,
        mono: dict[tuple[int, int], np.ndarray],
        ied_m: float,
        fs: float,
    ) -> tuple[float, float]:
        """Return (CV m/s, R²) for a given projection angle via anchor-first regression."""
        pairs = self._anchor_pairs(theta_deg, mono, ied_m)
        distances: list[float] = []
        delays: list[float] = []
        for pos_i, pos_j, dist in pairs:
            tau = self._xcorr_delay(mono[pos_i], mono[pos_j], fs)
            if tau is None or abs(tau) < 1e-9:
                continue
            cv_est = dist / abs(tau)
            if cv_est < self._MIN_CV_MS or cv_est > self._MAX_CV_MS:
                continue
            distances.append(dist)
            delays.append(tau)

        if len(delays) < self._MIN_VALID_PAIRS:
            return 0.0, 0.0

        d_arr = np.array(distances)
        t_arr = np.array(delays)

        if np.ptp(d_arr) < 1e-9:
            # All distances identical — estimate slope from mean ratio
            mean_d = float(np.mean(d_arr))
            mean_t = float(np.mean(t_arr))
            if abs(mean_t) < 1e-9 or abs(mean_d) < 1e-9:
                return 0.0, 0.0
            slope = mean_t / mean_d
            y_var = float(np.var(t_arr))
            r2 = max(0.0, 1.0 - y_var / (mean_t**2 + 1e-30))
        else:
            slope, _, r, _, _ = linregress(d_arr, t_arr)
            r2 = float(r**2)

        if abs(slope) < 1e-9:
            return 0.0, 0.0
        cv = float(np.clip(1.0 / abs(slope), self._MIN_CV_MS, self._MAX_CV_MS))
        return cv, float(r2)

    # ------------------------------------------------------------------
    # XCorr delay
    # ------------------------------------------------------------------

    def _xcorr_delay(
        self,
        s_i: np.ndarray,
        s_j: np.ndarray,
        fs: float,
    ) -> float | None:
        n_i = np.linalg.norm(s_i)
        n_j = np.linalg.norm(s_j)
        if n_i < 1e-12 or n_j < 1e-12:
            return None
        xc = correlate(s_i, s_j, mode="full") / (n_i * n_j)
        lag = int(np.argmax(xc)) - (len(s_j) - 1)
        return lag / fs

    # ------------------------------------------------------------------
    # IZ detection — adjacent-bin sign reversal
    # ------------------------------------------------------------------

    def _binned_adj_delays(
        self,
        theta_deg: float,
        mono: dict[tuple[int, int], np.ndarray],
        ied_m: float,
        fs: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Compute signed XCorr delays between consecutive projection bins.

        Bins electrodes at half-IED resolution, averages signals per bin,
        then XCorr adjacent bins.  Returns (delays_ms, bin_midpoint_positions_m).
        """
        theta = np.radians(theta_deg)
        bins: dict[int, list[np.ndarray]] = {}
        for (r, c), sig in mono.items():
            bin_key = int(round((r * np.sin(theta) + c * np.cos(theta)) * 2))
            bins.setdefault(bin_key, []).append(sig)

        sorted_bins = sorted(bins.items())
        bin_avg = [(k / 2.0 * ied_m, np.mean(sigs, axis=0)) for k, sigs in sorted_bins]

        delays_ms: list[float] = []
        positions_m: list[float] = []
        for i in range(len(bin_avg) - 1):
            p_i, sig_i = bin_avg[i]
            p_j, sig_j = bin_avg[i + 1]
            tau = self._xcorr_delay(sig_i, sig_j, fs)
            if tau is None:
                continue
            delays_ms.append(tau * 1000.0)
            positions_m.append((p_i + p_j) / 2.0)

        return np.array(delays_ms), np.array(positions_m)

    def _detect_iz(
        self,
        delays_ms: np.ndarray,
        positions_m: np.ndarray,
    ) -> float | None:
        """Find IZ as the first sign reversal in adjacent-bin delays.

        A sign reversal indicates that wave propagation direction reversed,
        marking the innervation zone (motor end-plate region).
        """
        if len(delays_ms) < 2:
            return None
        # Skip near-zero entries to avoid spurious reversals from noise
        thresh = max(float(np.max(np.abs(delays_ms))) * 0.1, 0.2)
        for k in range(len(delays_ms) - 1):
            d_k = delays_ms[k]
            d_k1 = delays_ms[k + 1]
            if abs(d_k) < thresh or abs(d_k1) < thresh:
                continue
            if d_k * d_k1 < 0:
                tau_k = abs(d_k)
                tau_k1 = abs(d_k1)
                frac = tau_k / (tau_k + tau_k1)
                return float(positions_m[k] + frac * (positions_m[k + 1] - positions_m[k]))
        return None
