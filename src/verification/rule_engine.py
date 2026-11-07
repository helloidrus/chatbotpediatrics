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


def _format_number(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _format_range(value_min: Any, value_max: Any, unit: str | None) -> str:
    if value_min is None and value_max is None:
        return unit or ""
    if value_min is None:
        return f"<= {_format_number(value_max)} {unit or ''}".strip()
    if value_max is None:
        return f">= {_format_number(value_min)} {unit or ''}".strip()
    if value_min == value_max:
        return f"{_format_number(value_min)} {unit or ''}".strip()
    return f"{_format_number(value_min)}-{_format_number(value_max)} {unit or ''}".strip()

def _base_result(status: str, claim: dict, rule: dict | None = None) -> dict:
    result = {
        "status": status,
        "rule_id": rule.get("rule_id") if rule else None,
        "claim_type": claim.get("claim_type"),
        "medicine": claim.get("medicine")
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

    seen_ids = {}
    valid_rules = []
    
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("rule_id", "")
        if rule_id == "string":
            continue
        if rule_id in seen_ids:
            logger.error(
                "Rule ID duplikat ditemukan: '%s'. "
                "Rule kedua diabaikan — periksa rule_base.json!",
                rule_id
            )
            continue
        seen_ids[rule_id] = True
        valid_rules.append(rule)
    
    logger.info("Memuat %d rule valid dari %s", len(valid_rules), path)
    return valid_rules


def _ranges_overlap(
    rule_min: Any,
    rule_max: Any,
    claim_min: Any,
    claim_max: Any,
    *,
    unknown_claim_matches_specific: bool = False,
) -> bool:
    r_min, r_max = _to_float(rule_min), _to_float(rule_max)
    c_min, c_max = _to_float(claim_min), _to_float(claim_max)

    # Jika rule tidak membatasi → cocok dengan semua klaim
    if r_min is None and r_max is None:
        return True
    
    # Jika rule membatasi tapi klaim tidak menyertakan batasan
    # → kembalikan berdasarkan unknown_claim_matches_specific
    NARROW_AGE_RULE_THRESHOLD_MONTHS = 3
    if c_min is None and c_max is None:
        # Keep very narrow age rules from matching generic claim entries without age context.
        rule_range = (r_max if r_max is not None else 999) - (
            r_min if r_min is not None else 0
        )
        if rule_range < NARROW_AGE_RULE_THRESHOLD_MONTHS:
            return False
        return unknown_claim_matches_specific

    return (r_max is None or c_min is None or c_min <= r_max) and (
        r_min is None or c_max is None or c_max >= r_min
    )


def _condition_matches(rule: dict, claim: dict) -> bool:
    rule_condition = rule.get("condition") or {}
    claim_condition = claim.get("condition") or {}

    # Cek field kategorikal.
    # Jika rule tidak menentukan field (None), maka dianggap cocok dengan nilai apapun di klaim (wildcard).
    # Namun jika rule menentukan nilai, maka klaim wajib memiliki nilai yang sama (setelah normalisasi).
    for field in ("disease", "phase", "severity", "complication"):
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


def _condition_specificity(rule: dict) -> int:
    condition = rule.get("condition") or {}
    score = 0
    for field in ("disease", "phase", "severity", "complication"):
        if condition.get(field) is not None:
            score += 1
    for field in ("age_month_min", "age_month_max", "weight_kg_min", "weight_kg_max"):
        if condition.get(field) is not None:
            score += 1
    return score


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
        if (
            _condition_matches(rule, claim)
            and _signature_matches(rule, claim, ignore_claim_type=ignore_claim_type)
        ):
            matches.append(rule)

    matches.sort(key=_condition_specificity, reverse=True)
    return matches


def _claim_range(claim: dict) -> tuple[float | None, float | None, Any]:
    return _to_float(claim.get("value_min")), _to_float(claim.get("value_max")), claim.get("unit")


def _rule_range(rule: dict) -> tuple[float | None, float | None, Any]:
    rule_claim = rule.get("claim") or {}
    return _to_float(rule_claim.get("value_min")), _to_float(rule_claim.get("value_max")), rule_claim.get("unit")


def _lower_bound_ok(claim_min: float | None, rule_min: float | None) -> bool:
    if rule_min is None:
        return True
    if claim_min is None:
        return rule_min <= 0
    return claim_min >= rule_min


def _upper_bound_ok(claim_max: float | None, rule_max: float | None) -> bool:
    if rule_max is None:
        return True
    if claim_max is None:
        return False
    return claim_max <= rule_max


def _verify_numeric(claim: dict, matched_rules: list[dict]) -> dict:
    claim_min, claim_max, claim_unit = _claim_range(claim)

    if claim_min is None and claim_max is None:
        result = _base_result("no_rule", claim)
        result["note"] = "Klaim numerik tidak memiliki nilai yang bisa dibandingkan."
        return result

    if claim_min is None and claim_max is not None:
        shape_matched_rules = [
            rule for rule in matched_rules
            if _rule_range(rule)[0] is None and _rule_range(rule)[1] is not None
        ]
    elif claim_min is not None and claim_max is None:
        shape_matched_rules = [
            rule for rule in matched_rules
            if _rule_range(rule)[0] is not None and _rule_range(rule)[1] is None
        ]
    else:
        shape_matched_rules = matched_rules

    if not shape_matched_rules:
        result = _base_result("uncovered", claim)
        result["claim_value"] = _format_range(claim_min, claim_max, claim_unit)
        result["note"] = "Tidak ada rule dengan bentuk batas yang sesuai untuk memverifikasi klaim."
        return result

    for rule in shape_matched_rules:
        rule_min, rule_max, rule_unit = _rule_range(rule)
        if claim_min is None and claim_max is not None:
            bounds_ok = _upper_bound_ok(claim_max, rule_max)
        elif claim_max is None and claim_min is not None:
            bounds_ok = _lower_bound_ok(claim_min, rule_min)
        else:
            bounds_ok = _lower_bound_ok(claim_min, rule_min) and _upper_bound_ok(
                claim_max, rule_max
            )

        if bounds_ok:
            result = _base_result("compliant", claim, rule)
            result["claim_value"] = _format_range(claim_min, claim_max, claim_unit)
            result["allowed_range"] = _format_range(rule_min, rule_max, rule_unit)
            return result

    highest_specificity = _condition_specificity(shape_matched_rules[0])
    best = next(
        rule
        for rule in shape_matched_rules
        if _condition_specificity(rule) == highest_specificity
    )
    best_min, best_max, best_unit = _rule_range(best)
    result = _base_result("violation", claim, best)
    result["claim_value"] = _format_range(claim_min, claim_max, claim_unit)
    result["allowed_range"] = _format_range(best_min, best_max, best_unit)
    return result


def verify_claims(claim_list: list[dict], rules: list[dict]) -> list[dict]:
    results: list[dict] = []

    for claim in claim_list:
        matched_rules = _matching_rules(claim, rules)
        if not matched_rules:
            result = _base_result("uncovered", claim)
            result["note"] = (
                "Klaim berada di luar cakupan rule yang tersedia. "
                "Diperlukan review manual oleh klinisi."
            )
            results.append(result)
            continue

        results.append(_verify_numeric(claim, matched_rules))

    violations = sum(1 for result in results if result["status"] == "violation")
    logger.info("Verifikasi selesai: %d klaim, %d pelanggaran.", len(results), violations)
    return results
