import json
import re


def load_rules(path="rule_pediatrics.json"):
    # Accept UTF-8 JSON files with or without a BOM marker.
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    return data["rules"]


def _norm_str(value):
    return str(value).strip().lower() if value is not None else None


def _norm_float(value):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        value = float(value)
        return int(value) if value.is_integer() else value
    except (TypeError, ValueError):
        return None


def _norm_unit(value):
    unit = _norm_str(value)
    if unit is None:
        return None

    unit_map = {
        "mg/kgbb": "mg/kg",
        "mg/kgbb/dose": "mg/kg/dose",
        "mg/kgbb/dosis": "mg/kg/dose",
        "mg_garam/kgbb/dose": "mg_garam/kg/dose",
        "mg_garam/kgbb/dosis": "mg_garam/kg/dose",
        "mg_basa/kgbb": "mg_basa/kg",
        "mg/kgbb_total_dose": "mg/kg_total_dose",
    }
    return unit_map.get(unit, unit)


def _normalize_disease(value):
    disease = _norm_str(value)
    disease_aliases = {
        "malaria vivax": "malaria vivax, malariae, dan ovale",
        "malaria malariae": "malaria vivax, malariae, dan ovale",
        "malaria ovale": "malaria vivax, malariae, dan ovale",
    }
    return disease_aliases.get(disease, disease)


def _parse_range_expr(value):
    text = _norm_str(value)
    if text is None:
        return None

    less_than = re.fullmatch(r"<\s*(\d+(?:[.,]\d+)?)", text)
    if less_than:
        return {"min": None, "max": _norm_float(less_than.group(1)), "max_inclusive": False}

    greater_than = re.fullmatch(r">\s*(\d+(?:[.,]\d+)?)", text)
    if greater_than:
        return {"min": _norm_float(greater_than.group(1)), "min_inclusive": False, "max": None}

    between = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)", text)
    if between:
        return {
            "min": _norm_float(between.group(1)),
            "min_inclusive": True,
            "max": _norm_float(between.group(2)),
            "max_inclusive": True,
        }

    exact = _norm_float(text)
    if exact is not None:
        return {"min": exact, "min_inclusive": True, "max": exact, "max_inclusive": True}

    return None


def _condition_value(condition, *keys):
    for key in keys:
        if key in condition:
            return condition[key]
    return None


def _matches_context_value(actual, expected):
    if expected is None:
        return True
    if actual is None:
        return False

    parsed_expected = _parse_range_expr(expected) if isinstance(expected, str) else None
    if parsed_expected:
        actual_value = _norm_float(actual)
        if actual_value is None:
            return False

        minimum = parsed_expected.get("min")
        maximum = parsed_expected.get("max")

        if minimum is not None:
            if parsed_expected.get("min_inclusive", True):
                if actual_value < minimum:
                    return False
            elif actual_value <= minimum:
                return False

        if maximum is not None:
            if parsed_expected.get("max_inclusive", True):
                if actual_value > maximum:
                    return False
            elif actual_value >= maximum:
                return False

        return True

    return actual == expected


def _matches_rule_condition(rule, claim, claim_json):
    condition = rule.get("condition") or {}
    claim_condition = claim_json.get("condition") or {}
    if not isinstance(claim_condition, dict):
        claim_condition = {}

    disease = _normalize_disease(claim_condition.get("disease"))
    rule_disease = _normalize_disease(condition.get("disease"))
    if rule_disease and disease != rule_disease:
        return False

    rule_age = _condition_value(condition, "age_months")
    if not _matches_context_value(claim_condition.get("age_months"), rule_age):
        return False

    rule_weight = condition.get("weight_kg")
    if not _matches_context_value(claim_condition.get("weight_kg"), rule_weight):
        return False

    if _norm_str(rule.get("claim_type")) != _norm_str(claim.get("claim_type")):
        return False

    if _norm_str(rule.get("parameter")) != _norm_str(claim.get("parameter")):
        return False

    constraint = rule.get("constraint") or {}
    claim_constraint = claim.get("constraint") or {}
    rule_unit = _norm_unit(constraint.get("unit"))
    claim_unit = _norm_unit(claim_constraint.get("unit"))
    if rule_unit and claim_unit != rule_unit:
        return False

    return True


def _build_numeric_result(rule, claim):
    constraint = rule.get("constraint") or {}
    claim_constraint = claim.get("constraint") or {}
    rule_min = constraint.get("min")
    rule_max = constraint.get("max")
    claim_min = claim_constraint.get("min")
    claim_max = claim_constraint.get("max")

    if claim_min is None and claim_max is None:
        return None

    if claim_min is None:
        claim_min = claim_max
    if claim_max is None:
        claim_max = claim_min

    result = {
        "rule_id": rule["rule_id"],
        "status": "pass",
        "claim_type": claim.get("claim_type"),
        "parameter": claim.get("parameter"),
        "llm_value": claim_min if claim_min == claim_max else [claim_min, claim_max],
        "llm_unit": claim_constraint.get("unit"),
    }

    if rule_min is None or rule_max is None:
        return result

    if claim_min < rule_min or claim_max > rule_max:
        result["status"] = "violation"
        result["allowed_range"] = [rule_min, rule_max]
        result["expected_unit"] = constraint.get("unit")

    return result


def verify_claim(claim, rule, claim_json):
    if not _matches_rule_condition(rule, claim, claim_json):
        return None
    return _build_numeric_result(rule, claim)


def verify_claims(claim_json, rules):
    results = []

    for claim in claim_json.get("claims", []):
        for rule in rules:
            verification = verify_claim(claim, rule, claim_json)
            if verification:
                results.append(verification)

    return results
