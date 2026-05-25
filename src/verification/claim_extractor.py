from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ONTOLOGY_PATH = Path(__file__).with_name("ontology.json")


def _canonical_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized or None


def _to_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Nilai numerik tidak valid dan diabaikan: %r", value)
        return None


def _normalize_with_alias(
    value: Any,
    aliases: dict[str, str],
    *,
    valid_set: set[str] | None = None,
    field_name: str = "unknown",
) -> str | None:
    key = _canonical_text(value)
    if key is None:
        return None

    resolved = aliases.get(key, key)

    if key not in aliases and valid_set is None:
        logger.warning(
            "Nilai %r tidak ditemukan di alias map untuk field %s; "
            "menggunakan canonical form %r tanpa validasi.",
            value,
            field_name,
            resolved,
        )

    if valid_set is not None and resolved not in valid_set:
        logger.warning("Nilai %r tidak valid untuk field %s; diabaikan.", value, field_name)
        return None

    return resolved


def _normalize_claim_type(value: Any) -> str | None:
    resolved = _normalize_with_alias(
        value,
        CLAIM_TYPE_ALIASES,
        valid_set=VALID_CLAIM_TYPE,
        field_name="claim_type",
    )
    if resolved is None:
        logger.warning("claim_type tidak valid atau hilang: %r", value)
    return resolved


def _clean_unit(value: Any) -> str | None:
    if value is None:
        return None
    unit = str(value).strip().lower()
    unit = re.sub(r"\s+", " ", unit)
    unit = unit.replace(" / ", "/").replace(" /", "/")
    return unit.replace("/ ", "/") or None


def _normalize_unit(value: Any) -> str | None:
    cleaned = _clean_unit(value)
    if cleaned is None:
        return None
    return UNIT_ALIASES.get(_canonical_text(cleaned), cleaned)


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _drop_none(item)) is not None
        }
    if isinstance(value, list):
        return [_drop_none(item) for item in value]
    return value


def _load_ontology(path: Path = ONTOLOGY_PATH) -> dict[str, dict[str, list[str]]]:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Ontology file tidak ditemukan: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ontology file tidak valid: {path}. Error: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Ontology file harus berisi JSON object, bukan {type(data).__name__}.")

    ontology: dict[str, dict[str, list[str]]] = {}
    for group_name, group_value in data.items():
        if not isinstance(group_value, dict):
            logger.warning("Grup ontology %s bukan object; diabaikan.", group_name)
            continue
        ontology[group_name] = {
            str(canonical): [str(a) for a in aliases]
            for canonical, aliases in group_value.items()
            if isinstance(aliases, list)
        }
    return ontology


def _build_alias_map(groups: dict[str, list[str]]) -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical, aliases in groups.items():
        key = _canonical_text(canonical)
        if key:
            alias_map[key] = canonical
        for alias in aliases:
            alias_key = _canonical_text(alias)
            if alias_key:
                alias_map[alias_key] = canonical
    return alias_map


ONTOLOGY = _load_ontology()


def _validate_ontology(ontology: dict) -> None:
    if not ontology:
        raise RuntimeError("Ontology kosong setelah loading.")

    critical_groups = {"claim_type", "disease", "medicine"}
    missing_groups = critical_groups - set(ontology)
    if missing_groups:
        logger.warning(
            "Ontology tidak memiliki beberapa grup kritis yang diharapkan: %s. "
            "Normalisasi untuk grup ini akan tidak efektif.",
            missing_groups,
        )


_validate_ontology(ONTOLOGY)

CLAIM_TYPE_ALIASES = _build_alias_map(ONTOLOGY.get("claim_type", {}))
PHASE_ALIASES      = _build_alias_map(ONTOLOGY.get("phase", {}))
SEVERITY_ALIASES   = _build_alias_map(ONTOLOGY.get("severity", {}))
PARAMETER_ALIASES  = _build_alias_map(ONTOLOGY.get("medicine", {}))
COMPLICATION_ALIASES = _build_alias_map(ONTOLOGY.get("complication", {}))
DISEASE_ALIASES    = _build_alias_map(ONTOLOGY.get("disease", {}))
UNIT_ALIASES       = _build_alias_map(ONTOLOGY.get("unit", {}))

# Valid sets derived directly from the ontology — no duplication needed.
VALID_CLAIM_TYPE = set(ONTOLOGY.get("claim_type", {}))
VALID_PHASE    = set(ONTOLOGY.get("phase", {}))
VALID_SEVERITY = set(ONTOLOGY.get("severity", {}))
VALID_DISEASE = set(ONTOLOGY.get("disease", {}))
VALID_COMPLICATION = set(ONTOLOGY.get("complication", {}))
VALID_MEDICINE = set(ONTOLOGY.get("medicine", {}))


def _extract_json_object(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()

    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[i:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    logger.error("Tidak menemukan object JSON valid dari output LLM. Input awal: %r", text[:300])
    return None


def _alias(raw: dict, field: str, aliases: dict[str, str], valid_set: set[str]) -> str | None:
    return _normalize_with_alias(raw.get(field), aliases, valid_set=valid_set, field_name=field)


def _parse_condition(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None

    result = {
        "disease": _alias(raw, "disease", DISEASE_ALIASES, VALID_DISEASE),
        "age_month_min": _to_float_or_none(raw.get("age_month_min")),
        "age_month_max": _to_float_or_none(raw.get("age_month_max")),
        "weight_kg_min": _to_float_or_none(raw.get("weight_kg_min")),
        "weight_kg_max": _to_float_or_none(raw.get("weight_kg_max")),
        "phase": _alias(raw, "phase", PHASE_ALIASES, VALID_PHASE),
        "severity": _alias(raw, "severity", SEVERITY_ALIASES, VALID_SEVERITY),
        "complication": _alias(raw, "complication", COMPLICATION_ALIASES, VALID_COMPLICATION),
        "category": _canonical_text(raw.get("category")),
    }

    age_min = result.get("age_month_min")
    age_max = result.get("age_month_max")
    if age_min is not None and age_max is not None and age_min > age_max:
        logger.error(
            "Range usia tidak valid: age_month_min (%s) > age_month_max (%s). "
            "Condition ditolak untuk keamanan klinis.",
            age_min,
            age_max,
        )
        return None

    return result


def _parse_claim(raw: Any, condition: dict) -> dict | None:
    if not isinstance(raw, dict):
        logger.warning("Claim bukan dict; dilewati: %r", raw)
        return None

    claim_type = _normalize_claim_type(raw.get("claim_type"))
    if claim_type is None:
        logger.warning("Klaim dilewati karena claim_type tidak valid: %r", raw)
        return None

    medicine = _normalize_with_alias(raw.get("medicine"), PARAMETER_ALIASES, valid_set=VALID_MEDICINE, field_name="medicine")
    if not medicine:
        logger.warning("Klaim dilewati karena field medicine tidak valid atau kosong: %r", raw)
        return None

    value_min = _to_float_or_none(raw.get("value_min"))
    value_max = _to_float_or_none(raw.get("value_max"))
    if value_min is not None and value_max is not None and value_min > value_max:
        logger.warning(
            "Range nilai terbalik untuk klaim: value_min=%r > value_max=%r; "
            "klaim dilewati karena semantik range tidak valid.",
            value_min, value_max,
        )
        return None

    evidence_text = str(raw.get("evidence_text") or "").strip() or None

    return _drop_none({
        "condition": condition,
        "claim_type": claim_type,
        "medicine": medicine,
        "value_min": value_min,
        "value_max": value_max,
        "unit": _normalize_unit(raw.get("unit")),
        "prohibited": True if claim_type == "contraindication" or raw.get("prohibited") is True else None,
        "evidence_text": evidence_text,
    })


def _parse_entry(entry: dict) -> list[dict]:
    condition = _parse_condition(entry.get("condition"))
    if not condition or all(value is None for value in condition.values()):
        logger.warning(
            "Entry dilewati karena condition tidak memiliki constraint yang valid "
            "(semua field kosong). Klaim tanpa kondisi bisa menyebabkan false positive: %r",
            entry,
        )
        return []

    claims_raw = entry.get("claims") or []
    if not isinstance(claims_raw, list):
        logger.warning("Field claims bukan list; entry dilewati: %r", entry)
        return []

    return [
        claim
        for raw_claim in claims_raw
        if (claim := _parse_claim(raw_claim, condition)) is not None
    ]


def extract_claims(llm_json_output: str) -> list[dict]:
    """
    Return normalised claims extracted from an LLM JSON output string.

    Raises RuntimeError if ontology initialization failed.
    """
    if not ONTOLOGY:
        raise RuntimeError(
            "ONTOLOGY tidak tersedia untuk normalisasi klaim! "
            "Ini terjadi saat module initialization. "
            "Periksa logs untuk error saat loading ontology.json."
        )

    if not llm_json_output:
        return []

    data = _extract_json_object(llm_json_output)
    if data is None:
        return []

    entries = data.get("entries")
    if not isinstance(entries, list):
        logger.warning("Output LLM tidak memiliki field 'entries' berbentuk list.")
        return []

    all_claims = [
        claim
        for entry in entries
        if isinstance(entry, dict)
        for claim in _parse_entry(entry)
    ]

    logger.info("Total klaim berhasil diekstrak: %d", len(all_claims))
    return all_claims
