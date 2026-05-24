from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", "_", str(value).strip().lower().replace("-", "_"))
    return normalized or None


def _same_norm(left: Any, right: Any) -> bool:
    return _norm(left) == _norm(right)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Nilai numerik tidak valid dan diabaikan: %r", value)
        return None


def _format_range(value_min: Any, value_max: Any, unit: str | None) -> str:
    if value_min is None and value_max is None:
        return unit or ""
    if value_min == value_max:
        return f"{value_min} {unit or ''}".strip()
    return f"{value_min}-{value_max} {unit or ''}".strip()


def _base_result(status: str, claim: dict, rule: dict | None = None) -> dict:
    result = {
        "status": status,
        "rule_id": rule.get("rule_id") if rule else None,
        "claim_type": claim.get("claim_type"),
        "medicine": claim.get("medicine"),
        "evidence_text": claim.get("evidence_text", ""),
    }
    if rule and (dose_context := (rule.get("claim") or {}).get("dose_context")) is not None:
        result["expected_dose_context"] = dose_context
    return result


def load_rules(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)

    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError(f"Field 'rules' di {path} harus berupa list.")

    valid_rules = [
        rule for rule in rules
        if isinstance(rule, dict) and rule.get("rule_id") != "string"
    ]
    logger.info("Berhasil memuat %d rule dari %s", len(valid_rules), path)
    return valid_rules


def _ranges_overlap(rule_min: Any, rule_max: Any, claim_min: Any, claim_max: Any) -> bool:
    r_min, r_max = _to_float(rule_min), _to_float(rule_max)
    c_min, c_max = _to_float(claim_min), _to_float(claim_max)

    if r_min is None and r_max is None:
        return True
    if c_min is None and c_max is None:
        return False

    return (r_max is None or c_min is None or c_min <= r_max) and (
        r_min is None or c_max is None or c_max >= r_min
    )


def _condition_matches(rule: dict, claim: dict) -> bool:
    rule_condition = rule.get("condition") or {}
    claim_condition = claim.get("condition") or {}

    for field in ("disease", "phase", "severity", "complication", "category"):
        rule_value = rule_condition.get(field)
        if rule_value is not None and not _same_norm(rule_value, claim_condition.get(field)):
            return False

    return _ranges_overlap(
        rule_condition.get("age_month_min"),
        rule_condition.get("age_month_max"),
        claim_condition.get("age_month_min"),
        claim_condition.get("age_month_max"),
    ) and _ranges_overlap(
        rule_condition.get("weight_kg_min"),
        rule_condition.get("weight_kg_max"),
        claim_condition.get("weight_kg_min"),
        claim_condition.get("weight_kg_max"),
    )


def _signature_matches(rule: dict, claim: dict, *, ignore_claim_type: bool = False) -> bool:
    rule_claim = rule.get("claim") or {}
    if not ignore_claim_type and not _same_norm(rule_claim.get("claim_type"), claim.get("claim_type")):
        return False

    rule_parameter = _norm(rule_claim.get("parameter") or rule_claim.get("medicine"))
    claim_parameter = _norm(claim.get("medicine"))
    return bool(rule_parameter and claim_parameter and rule_parameter == claim_parameter)


def _matching_rules(
    claim: dict,
    rules: list[dict],
    *,
    claim_type: str | None = None,
    ignore_claim_type: bool = False,
) -> list[dict]:
    matches = []
    for rule in rules:
        rule_claim = rule.get("claim") or {}
        if claim_type and _norm(rule_claim.get("claim_type")) != claim_type:
            continue
        if _condition_matches(rule, claim) and _signature_matches(rule, claim, ignore_claim_type=ignore_claim_type):
            matches.append(rule)
    return matches


def _claim_range(claim: dict) -> tuple[float | None, float | None, Any]:
    return _to_float(claim.get("value_min")), _to_float(claim.get("value_max")), claim.get("unit")


def _rule_range(rule: dict) -> tuple[float | None, float | None, Any]:
    rule_claim = rule.get("claim") or {}
    return _to_float(rule_claim.get("value_min")), _to_float(rule_claim.get("value_max")), rule_claim.get("unit")


def _unit_comparable(rule_unit: Any, claim_unit: Any) -> bool:
    return not (rule_unit and claim_unit) or _same_norm(rule_unit, claim_unit)


def _verify_numeric(claim: dict, matched_rules: list[dict]) -> dict:
    claim_min, claim_max, claim_unit = _claim_range(claim)
    if claim_min is None and claim_max is None:
        result = _base_result("no_rule", claim)
        result["note"] = "Klaim numerik tidak memiliki nilai yang bisa dibandingkan."
        return result

    if (claim_min is None) != (claim_max is None):
        logger.warning(
            "Klaim memiliki hanya satu bound numerik (min=%r, max=%r); "
            "semantik range dapat ambigu.",
            claim_min,
            claim_max,
        )

    comparable_rules = [
        rule for rule in matched_rules
        if _unit_comparable(_rule_range(rule)[2], claim_unit)
    ]

    for rule in comparable_rules:
        rule_min, rule_max, rule_unit = _rule_range(rule)
        min_ok = claim_min is None or rule_min is None or claim_min >= rule_min
        max_ok = claim_max is None or rule_max is None or claim_max <= rule_max
        if min_ok and max_ok:
            result = _base_result("compliant", claim, rule)
            result["claim_value"] = _format_range(claim_min, claim_max, claim_unit)
            result["allowed_range"] = _format_range(rule_min, rule_max, rule_unit)
            return result

    best = comparable_rules[0] if comparable_rules else matched_rules[0]
    best_min, best_max, best_unit = _rule_range(best)
    result = _base_result("violation", claim, best)
    result["claim_value"] = _format_range(claim_min, claim_max, claim_unit)
    result["allowed_range"] = _format_range(best_min, best_max, best_unit)
    if not comparable_rules:
        result["note"] = "Unit klaim tidak sama dengan rule yang cocok."
    return result


def _verify_contraindication(claim: dict, matched_rules: list[dict]) -> dict:
    contra_rules = [
        rule for rule in matched_rules
        if (rule.get("claim") or {}).get("prohibited") is True
    ]
    if contra_rules:
        result = _base_result("compliant", claim, contra_rules[0])
        result["expected"] = "prohibited"
        return result

    result = _base_result("no_rule", claim)
    result["note"] = "Tidak ada rule contraindication untuk klaim ini. Status contraindication tidak terkonfirmasi."
    return result


def verify_claims(claims: list[dict], rules: list[dict]) -> list[dict]:
    results: list[dict] = []

    for claim in claims:
        contra_rules = [
            rule for rule in _matching_rules(claim, rules, claim_type="contraindication", ignore_claim_type=True)
            if (rule.get("claim") or {}).get("prohibited") is True
        ]
        if contra_rules and claim.get("claim_type") != "contraindication":
            result = _base_result("violation", claim, contra_rules[0])
            result["expected"] = "prohibited"
            result["claim_value"] = "recommended_or_mentioned"
            result["note"] = "Klaim menyebut medicine yang dikontraindikasikan pada kondisi ini."
            results.append(result)
            continue

        matched_rules = _matching_rules(claim, rules)
        if not matched_rules:
            result = _base_result("no_rule", claim)
            result["note"] = "Tidak ada rule yang cocok ditemukan untuk klaim ini."
            results.append(result)
            continue

        if claim.get("claim_type") == "contraindication":
            results.append(_verify_contraindication(claim, matched_rules))
        else:
            results.append(_verify_numeric(claim, matched_rules))

    violations = sum(1 for result in results if result["status"] == "violation")
    logger.info("Verifikasi selesai: %d klaim, %d pelanggaran.", len(results), violations)
    return results
