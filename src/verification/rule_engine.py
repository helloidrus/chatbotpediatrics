from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit alias table
# ---------------------------------------------------------------------------

_UNIT_ALIASES: dict[str, str] = {
    "kali sehari":       "kali/hari",
    "kali per hari":     "kali/hari",
    "x sehari":          "kali/hari",
    "x per hari":        "kali/hari",
    "x/hari":            "kali/hari",
    "per hari":          "kali/hari",
    "hari":              "hari",
    "jam":               "jam",
    "mg/kg":             "mg/kgbb",
    "mg/kg bb":          "mg/kgbb",
    "mg per kg":         "mg/kgbb",
    "mg per kgbb":       "mg/kgbb",
    "mg/kg/hari":        "mg/kgbb/hari",
    "mg/kg bb/hari":     "mg/kgbb/hari",
    "mg/kg per hari":    "mg/kgbb/hari",
    "mg/kg/kali":        "mg/kgbb/kali",
    "mg/kg bb/kali":     "mg/kgbb/kali",
    "mg/kg/dosis":       "mg/kgbb/kali",
    "mg/kgbb/dosis":     "mg/kgbb/kali",
    "mg/kg/dose":        "mg/kgbb/kali",
    "mg/kgbb/dose":      "mg/kgbb/kali",
    "mg/kgbb/dose":      "mg/kgbb/kali",
    "mg/kgbb/":          "mg/kgbb/kali",
    "mg garam/kgbb/dose":      "mggaram/kgbb/kali",
    "ml/kg":             "mL/kgbb",
    "ml/kg bb":          "mL/kgbb",
    "ml/kgbb":           "mL/kgbb",
    "ml/kg/kali":        "mL/kgbb/kali",
    "ml/kg bb/kali":     "mL/kgbb/kali",
    "ml/kgbb/kali":      "mL/kgbb/kali",
    "ml/kg/hari":        "mL/kgbb/hari",
    "ml/kg bb/hari":     "mL/kgbb/hari",
    "ml/kgbb/hari":      "mL/kgbb/hari",
    "ml/kg/jam":         "mL/kgbb/jam",
    "ml/kg bb/jam":      "mL/kgbb/jam",
    "ml/kgbb/jam":       "mL/kgbb/jam",
    "ml":                "mL",
    "iu/kgbb/kali":      "IU/kgbb/kali",
    "iu/kali":           "IU/kali",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(value: Any) -> str | None:
    """Lowercase + collapse whitespace + underscore-separate. Returns None if empty."""
    if value is None:
        return None
    s = re.sub(r"\s+", "_", str(value).strip().lower().replace("-", "_"))
    return s or None


def _normalize_unit(value: Any) -> str | None:
    if value is None:
        return None
    unit = re.sub(r"\s+", " ", str(value).strip().lower())
    unit = unit.replace(" / ", "/").replace(" /", "/").replace("/ ", "/")
    return _UNIT_ALIASES.get(unit, unit)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_range(value_min: Any, value_max: Any, unit: str | None) -> str:
    if value_min is None and value_max is None:
        return unit or ""
    if value_min == value_max:
        return f"{value_min} {unit or ''}".strip()
    return f"{value_min}-{value_max} {unit or ''}".strip()


def _base_result(status: str, claim: dict, rule: dict | None = None) -> dict:
    result = {
        "status":        status,
        "rule_id":       rule.get("rule_id") if rule else None,
        "claim_type":    claim.get("claim_type"),
        "parameter":     claim.get("parameter"),
        "route":         claim.get("route"),
        "dose_context":  claim.get("dose_context"),
        "evidence_text": claim.get("evidence_text", ""),
    }
    if rule:
        rule_dose_context = (rule.get("claim") or {}).get("dose_context")
        if rule_dose_context is not None:
            result["expected_dose_context"] = rule_dose_context
    return result


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------

def load_rules(path: str) -> list[dict]:
    """Load rule_pediatrics.json and drop the schema/template row."""
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


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _ranges_overlap(
    rule_min: Any, rule_max: Any,
    claim_min: Any, claim_max: Any,
) -> bool:
    r_min, r_max = _to_float(rule_min), _to_float(rule_max)
    c_min, c_max = _to_float(claim_min), _to_float(claim_max)

    if r_min is None and r_max is None:
        return True
    if c_min is None and c_max is None:
        return False

    c_min = c_min if c_min is not None else c_max
    c_max = c_max if c_max is not None else c_min

    return (r_max is None or c_min <= r_max) and (r_min is None or c_max >= r_min)


def _condition_matches(rule: dict, claim: dict) -> bool:
    rc = rule.get("condition") or {}
    cc = claim.get("condition") or {}

    for field in ("disease", "phase", "severity", "complication"):
        rule_val = _norm(rc.get(field))
        if rule_val is not None and rule_val != _norm(cc.get(field)):
            return False

    if not _ranges_overlap(
        rc.get("age_month_min"), rc.get("age_month_max"),
        cc.get("age_month_min"), cc.get("age_month_max"),
    ):
        return False

    return _ranges_overlap(
        rc.get("weight_kg_min"), rc.get("weight_kg_max"),
        cc.get("weight_kg_min"), cc.get("weight_kg_max"),
    )


def _signature_matches(rule: dict, claim: dict, *, ignore_claim_type: bool = False) -> bool:
    rule_claim = rule.get("claim") or {}

    if not ignore_claim_type:
        if _norm(rule_claim.get("claim_type")) != _norm(claim.get("claim_type")):
            return False

    rule_param = _norm(rule_claim.get("parameter")) or ""
    claim_param = _norm(claim.get("parameter")) or ""
    if not (rule_param and claim_param and (rule_param in claim_param or claim_param in rule_param)):
        return False

    rule_route = _norm(rule_claim.get("route"))
    if rule_route in (None, "any"):
        return True

    claim_route = _norm(claim.get("route"))
    if claim_route not in (None, "any") and rule_route != claim_route:
        return False

    rule_dose_context = _norm(rule_claim.get("dose_context"))
    if rule_dose_context is None:
        return True

    return rule_dose_context == _norm(claim.get("dose_context"))


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _verify_numeric(claim: dict, matched_rules: list[dict]) -> dict:
    claim_min = claim.get("value_min")
    claim_max = claim.get("value_max")
    claim_unit = _normalize_unit(claim.get("unit"))

    if claim_min is None and claim_max is None:
        result = _base_result("no_rule", claim)
        result["note"] = "Klaim numerik tidak memiliki nilai yang bisa dibandingkan."
        return result

    comparable_rules = []
    for rule in matched_rules:
        rule_claim = rule.get("claim") or {}
        rule_unit = _normalize_unit(rule_claim.get("unit"))
        if rule_unit and claim_unit and rule_unit != claim_unit:
            continue
        comparable_rules.append(rule)

        rule_min = rule_claim.get("value_min")
        rule_max = rule_claim.get("value_max")
        if (claim_min is None or rule_min is None or claim_min >= rule_min) and \
           (claim_max is None or rule_max is None or claim_max <= rule_max):
            result = _base_result("compliant", claim, rule)
            result["claim_value"]   = _format_range(claim_min, claim_max, claim_unit)
            result["allowed_range"] = _format_range(rule_min, rule_max, rule_unit)
            return result

    best = comparable_rules[0] if comparable_rules else matched_rules[0]
    best_claim = best.get("claim") or {}
    best_unit = _normalize_unit(best_claim.get("unit"))

    result = _base_result("violation", claim, best)
    result["claim_value"]   = _format_range(claim_min, claim_max, claim_unit)
    result["allowed_range"] = _format_range(best_claim.get("value_min"), best_claim.get("value_max"), best_unit)
    if not comparable_rules:
        result["note"] = "Unit klaim tidak sama dengan rule yang cocok."
    return result


def _verify_contraindication(claim: dict, matched_rules: list[dict]) -> dict:
    for rule in matched_rules:
        if (rule.get("claim") or {}).get("prohibited") is True and claim.get("prohibited") is True:
            result = _base_result("compliant", claim, rule)
            result["expected"] = "prohibited"
            return result

    result = _base_result("violation", claim, matched_rules[0])
    result["expected"]    = "prohibited"
    result["claim_value"] = "not_prohibited"
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_claims(claims: list[dict], rules: list[dict]) -> list[dict]:
    """Verify each normalised claim against the rule list."""
    results: list[dict] = []

    for claim in claims:
        # Check for contraindication rules that apply to this claim's parameter/condition.
        contra_rules = [
            rule for rule in rules
            if _norm((rule.get("claim") or {}).get("claim_type")) == "contraindication"
            and (rule.get("claim") or {}).get("prohibited") is True
            and _condition_matches(rule, claim)
            and _signature_matches(rule, claim, ignore_claim_type=True)
        ]

        if contra_rules and claim.get("claim_type") != "contraindication":
            result = _base_result("violation", claim, contra_rules[0])
            result["expected"]    = "prohibited"
            result["claim_value"] = "recommended_or_mentioned"
            result["note"]        = "Klaim menyebut parameter yang dikontraindikasikan pada kondisi ini."
            results.append(result)
            continue

        matched_rules = [
            rule for rule in rules
            if _condition_matches(rule, claim) and _signature_matches(rule, claim)
        ]

        if not matched_rules:
            result = _base_result("no_rule", claim)
            result["note"] = "Tidak ada rule yang cocok ditemukan untuk klaim ini."
            results.append(result)
            continue

        if claim.get("claim_type") == "contraindication":
            results.append(_verify_contraindication(claim, matched_rules))
        else:
            results.append(_verify_numeric(claim, matched_rules))

    violations = sum(1 for r in results if r["status"] == "violation")
    logger.info("Verifikasi selesai: %d klaim, %d pelanggaran.", len(results), violations)
    return results
