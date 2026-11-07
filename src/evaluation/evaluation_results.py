from math import comb

import pandas as pd
from scipy.stats import binomtest
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parent
QUERY_CSV_PATH = EVALUATION_DIR / "queries_outputs.csv"
CLAIMS_CSV_PATH = EVALUATION_DIR / "claims.csv"


def mcnemar_exact_manual(b, c):
    """p-value exact dua sisi: min(1, 2 * P(X <= min(b, c))), X ~ Bin(b + c, 0.5)."""
    n = b + c
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def mcnemar_exact(b, c):
    """Sama dengan versi manual, memakai scipy.stats.binomtest."""
    if b + c == 0:
        return 1.0
    return float(binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue)


def paired_table(baseline_halu, verified_halu):
    """Bangun (a, b, c, d) dari dua deret boolean (True = halusinasi)."""
    assert len(baseline_halu) == len(verified_halu)
    pairs = list(zip(baseline_halu, verified_halu))
    a = sum(1 for x, y in pairs if not x and not y)
    b = sum(1 for x, y in pairs if x and not y)      # improved
    c = sum(1 for x, y in pairs if not x and y)      # worsened
    d = sum(1 for x, y in pairs if x and y)
    return a, b, c, d


def baca_csv(file_path):
    return pd.read_csv(
        file_path,
        sep=None,
        engine="python",
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig",
    )


def format_p_value(value):
    precision = 4 if value < 0.01 else 2
    return f"{value:.{precision}f}"


def main():
    claims = baca_csv(CLAIMS_CSV_PATH)
    required_claim_columns = {"query_id", "claim_correct", "status", "outcome"}
    missing_columns = required_claim_columns - set(claims.columns)
    if missing_columns:
        raise ValueError(
            f"Kolom tidak ditemukan di {CLAIMS_CSV_PATH}: {sorted(missing_columns)}"
        )
    claims["query_id"] = claims["query_id"].str.strip()
    claims = claims[claims["query_id"].ne("")].copy()
    claims["claim_correct"] = claims["claim_correct"].str.strip().str.upper()
    claims["status"] = claims["status"].str.strip().str.casefold()
    claims["outcome"] = claims["outcome"].str.strip().str.upper()
    if "claim_idx" in claims.columns and claims.duplicated(
        ["query_id", "claim_idx"]
    ).any():
        raise ValueError("Pasangan query_id/claim_idx ganda di claims.csv")

    q = baca_csv(QUERY_CSV_PATH)
    required_columns = {
        "query_id",
        "baseline_correct",
        "selfcorrection_correct",
        "verification_correct",
        "verification_decision",
    }
    missing_columns = required_columns - set(q.columns)
    if missing_columns:
        raise ValueError(
            f"Kolom tidak ditemukan di {QUERY_CSV_PATH}: {sorted(missing_columns)}"
        )
    q["query_id"] = q["query_id"].str.strip()
    q = q[q["query_id"].ne("")].copy()
    if q["query_id"].duplicated().any():
        raise ValueError("ID query ganda di queries_outputs.csv")

    query_ids = set(q["query_id"])
    claim_query_ids = set(claims["query_id"])
    if query_ids != claim_query_ids:
        missing_claim_ids = sorted(query_ids - claim_query_ids)
        unexpected_claim_ids = sorted(claim_query_ids - query_ids)
        raise ValueError(
            "ID query pada claims.csv dan queries_outputs.csv berbeda; "
            f"tanpa klaim={missing_claim_ids}, ID tambahan={unexpected_claim_ids}"
        )

    correctness_columns = (
        "baseline_correct",
        "selfcorrection_correct",
        "verification_correct",
    )
    for col in correctness_columns:
        q[col] = q[col].str.strip().str.upper()
        unknown_values = set(q[col]) - {"TRUE", "FALSE"}
        if unknown_values:
            raise ValueError(f"Nilai tak dikenal di {col}: {sorted(unknown_values)}")

    baseline = q["baseline_correct"]
    selfcorrection = q["selfcorrection_correct"]
    verification = q["verification_correct"]

    # FALSE = jawaban salah (halusinasi numerik); TRUE = jawaban benar.
    N = len(q)
    base_halu = baseline.eq("FALSE")
    selfcorrection_halu = selfcorrection.eq("FALSE")
    verification_halu = verification.eq("FALSE")
    baseline_total = int(base_halu.sum())
    selfcorrection_total = int(selfcorrection_halu.sum())
    verification_total = int(verification_halu.sum())
    verification_improved = int((base_halu & verification.eq("TRUE")).sum())
    verification_worsened = int((baseline.eq("TRUE") & verification_halu).sum())
    selfcorrection_improved = int((base_halu & selfcorrection.eq("TRUE")).sum())
    selfcorrection_worsened = int((baseline.eq("TRUE") & selfcorrection_halu).sum())

    item_count = len(claims)
    none_count = int(claims["claim_correct"].eq("NO CLAIM").sum())
    claim_count = item_count - none_count
    covered = claims["status"].isin({"compliant", "violation"})
    covered_count = int(covered.sum())
    uncovered_count = item_count - covered_count
    outcomes = claims.loc[covered, "outcome"]
    confusion = {key: int(outcomes.eq(key).sum()) for key in ("TP", "FN", "FP", "TN")}
    unknown_outcomes = set(outcomes) - set(confusion)
    if unknown_outcomes:
        raise ValueError(f"Outcome tidak dikenal pada item covered: {sorted(unknown_outcomes)}")
    if sum(confusion.values()) != covered_count:
        raise ValueError("Confusion matrix tidak sesuai dengan jumlah covered items")

    tp, fn, fp, tn = (confusion[key] for key in ("TP", "FN", "FP", "TN"))
    recall_denominator = tp + fn
    precision_denominator = tp + fp
    recall = tp / recall_denominator if recall_denominator else 0.0
    precision = tp / precision_denominator if precision_denominator else 0.0
    accuracy = (tp + tn) / covered_count if covered_count else 0.0
    f1_denominator = 2 * tp + fp + fn
    f1 = 2 * tp / f1_denominator if f1_denominator else 0.0

    verification_p = mcnemar_exact(verification_improved, verification_worsened)
    selfcorrection_p = mcnemar_exact(selfcorrection_improved, selfcorrection_worsened)
    if abs(
        mcnemar_exact_manual(verification_improved, verification_worsened)
        - verification_p
    ) >= 1e-12:
        raise AssertionError("Perhitungan p-value McNemar tidak konsisten")
    if abs(
        mcnemar_exact_manual(selfcorrection_improved, selfcorrection_worsened)
        - selfcorrection_p
    ) >= 1e-12:
        raise AssertionError("Perhitungan p-value McNemar tidak konsisten")

    rows = [
        (f"Evaluation items ({len(q)} queries)", f"{item_count} ({claim_count} claims + {none_count} none)"),
        ("Covered / uncovered items", f"{covered_count} ({covered_count / item_count * 100:.1f}%) / {uncovered_count}"),
        ("True positive / false negative / false positive / true negative (covered)", f"{tp} / {fn} / {fp} / {tn}"),
        ("Recall, covered claims", f"{recall * 100:.1f}% ({tp}/{recall_denominator})"),
        ("Precision, covered claims", f"{precision * 100:.1f}% ({tp}/{precision_denominator})"),
        ("Accuracy / F1", f"{accuracy * 100:.1f}% ({tp + tn}/{covered_count}) / {f1 * 100:.1f}%"),
        ("Hallucinated queries (baseline)", f"{baseline_total}/{N} ({baseline_total / N * 100:.1f}%)"),
        ("Hallucinated queries (self-correction)", f"{selfcorrection_total}/{N} ({selfcorrection_total / N * 100:.1f}%)"),
        ("Hallucinated queries (verification)", f"{verification_total}/{N} ({verification_total / N * 100:.1f}%)"),
        ("Improved / worsened (verification)", f"{verification_improved} / {verification_worsened} (p = {format_p_value(verification_p)})"),
        ("Improved / worsened (self-correction)", f"{selfcorrection_improved} / {selfcorrection_worsened} (p = {format_p_value(selfcorrection_p)})"),
    ]

    print("Coverage, Claim-Level Detection, and Query-Level Results")
    print(f"{'Measure':<78} Value")
    print("-" * 112)
    for measure, value in rows:
        print(f"{measure:<78} {value}")


if __name__ == "__main__":
    main()
