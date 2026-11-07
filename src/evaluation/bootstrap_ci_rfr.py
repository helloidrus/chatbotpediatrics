"""Bootstrap 95% CI untuk Rule Faithfulness Rate (RFR), RQ1.

RFR = (N_FF + 0.5 * N_PM) / N * 100
Skor per aturan: Fully Faithful = 1.0, Partial Match = 0.5, Unfaithful = 0.0.
"""
import numpy as np
import pandas as pd
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent / "audit_100_aturan.csv"
N_BOOT = 20000
SEED = 42
ALPHA = 0.05


def rfr(scores):
    """RFR (%) dari skor per aturan. Dengan skor 1.0/0.5/0.0 identik dengan
    (N_FF + 0.5 * N_PM) / N * 100."""
    return float(np.mean(scores) * 100)


def bootstrap_ci(scores, n_boot=N_BOOT, alpha=ALPHA, seed=SEED):
    """Bootstrap persentil: resampling skor per aturan dengan pengembalian,
    hitung RFR tiap resample, ambil persentil alpha/2 dan 1 - alpha/2."""
    scores = np.asarray(scores, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(scores), size=(n_boot, len(scores)))
    boot = scores[idx].mean(axis=1) * 100
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


if __name__ == "__main__":
    score_column = pd.read_csv(CSV_PATH, encoding="utf-8-sig", sep=";")["Status_Faithfulness"]
    scores = pd.to_numeric(score_column, errors="raise").dropna().to_numpy()
    if len(scores) == 0:
        raise ValueError(f"No reviewed scores found in {CSV_PATH!r}")
    n = len(scores)
    n_ff = int((scores == 1.0).sum())
    n_pm = int((scores == 0.5).sum())
    n_uf = int((scores == 0.0).sum())
    assert n_ff + n_pm + n_uf == n, "Ada skor di luar 1.0 / 0.5 / 0.0"

    lo, hi = bootstrap_ci(scores)
    print(f"N = {n}  (FF {n_ff}, PM {n_pm}, UF {n_uf})")
    print(f"RFR = ({n_ff} + 0.5 x {n_pm}) / {n} x 100 = {rfr(scores):.1f}%")
    print(f"95% bootstrap CI ({N_BOOT:,} resamples, seed {SEED}): {lo:.1f}-{hi:.1f}%")
