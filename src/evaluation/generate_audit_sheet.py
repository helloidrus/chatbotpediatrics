import csv
import json
import random
from pathlib import Path


def buat_lembar_kerja_audit(
    file_json_ai,
    output_csv="audit_manual_100_aturan.csv",
    n_sample=100,
):
    with open(file_json_ai, "r", encoding="utf-8") as f:
        data = json.load(f)
        rules = data.get("rules", data) if isinstance(data, dict) else data

    # Gunakan generator lokal agar hasil konsisten tanpa mengubah random global.
    rng = random.Random(42)
    sampel_rules = rng.sample(rules, min(n_sample, len(rules)))

    headers = [
        "No",
        "Rule_ID",
        "Disease",
        "Age_Month_Min",
        "Age_Month_Max",
        "Weight_Kg_Min",
        "Weight_Kg_Max",
        "Phase",
        "Severity",
        "Complication",
        "Claim_Type",
        "Medicine",
        "Value_Min",
        "Value_Max",
        "Unit",
        "Metadata_Source",
        "Metadata_Section",
        "Metadata_Page",
        "Metadata_Text",
        "Status_Faithfulness",
        "Kode_Error",
        "Catatan_Audit_Klinis",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for idx, rule in enumerate(sampel_rules, start=1):
            cond = rule.get("condition") or {}
            claim = rule.get("claim") or {}
            meta = rule.get("metadata") or {}

            writer.writerow(
                [
                    idx,
                    rule.get("rule_id", ""),
                    cond.get("disease", ""),
                    cond.get("age_month_min", ""),
                    cond.get("age_month_max", ""),
                    cond.get("weight_kg_min", ""),
                    cond.get("weight_kg_max", ""),
                    cond.get("phase", ""),
                    cond.get("severity", ""),
                    cond.get("complication", ""),
                    claim.get("claim_type", ""),
                    claim.get("medicine", ""),
                    claim.get("value_min", ""),
                    claim.get("value_max", ""),
                    claim.get("unit", ""),
                    meta.get("source", ""),
                    meta.get("section", ""),
                    meta.get("page", ""),
                    meta.get("text", ""),
                    "",
                    "",
                    "",
                ]
            )

    print(
        f"Lembar kerja audit berhasil dibuat: '{output_csv}' "
        f"({len(sampel_rules)} aturan sampel)."
    )


if __name__ == "__main__":
    rules_dir = Path(__file__).resolve().parents[2] / "data" / "rules"
    file_json_ai = rules_dir / "rule_pediatrics_nlm.json"
    output_csv = rules_dir / "audit_manual_100_aturan.csv"
    buat_lembar_kerja_audit(file_json_ai, output_csv)