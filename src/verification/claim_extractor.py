from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ONTOLOGY_PATH = Path(__file__).resolve().parents[2] / "data" / "rules" / "ontology.json"


def _canonical_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized or None


def _canonical_unit_text(value: Any) -> str | None:
    if value is None:
        return None
    unit = str(value).strip().lower()
    # Normalisasi: hapus spasi di sekitar slash
    unit = re.sub(r'\s*/\s*', '/', unit)
    # Normalisasi: 'kg bb' → 'kgbb' dan 'kgBB' → 'kgbb'
    unit = re.sub(r'kg\s+bb', 'kgbb', unit, flags=re.IGNORECASE)
    # Pertahankan pemisah kata sebagai underscore agar cocok dengan alias ontology
    unit = re.sub(r'\s+', '_', unit)
    return unit or None


def _to_float_or_none(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            cleaned = value.strip().lower().replace(",", ".")
            cleaned = re.sub(r"\s+", "", cleaned)
            if cleaned.endswith("kg"):
                cleaned = cleaned[:-2]
            elif cleaned.endswith("g"):
                cleaned = cleaned[:-1]
            value = cleaned
        number = float(value)
        if number.is_integer():
            return int(number)
        return number
    except (TypeError, ValueError):
        return None


def _normalize_weight_kg(value: Any) -> int | float | None:
    normalized = _to_float_or_none(value)
    if normalized is None:
        return None
    if normalized > 100:
        normalized = normalized / 1000
        logger.debug("Mengonversi berat dari gram ke kg: %r -> %s", value, normalized)
    return normalized


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

    if valid_set is not None and resolved not in valid_set:
        return None

    return resolved


def _normalize_claim_type(value: Any) -> str | None:
    resolved = _normalize_with_alias(
        value,
        CLAIM_TYPE_ALIASES,
        valid_set=VALID_CLAIM_TYPE,
        field_name="claim_type",
    )
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
    canonical = _canonical_unit_text(cleaned)
    return UNIT_ALIASES.get(canonical, cleaned)


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
        return


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

    disease = _alias(raw, "disease", DISEASE_ALIASES, VALID_DISEASE)
    raw_disease = raw.get("disease")
    result = {
        "disease": disease,
        "age_month_min": _to_float_or_none(raw.get("age_month_min")),
        "age_month_max": _to_float_or_none(raw.get("age_month_max")),
        "weight_kg_min": _normalize_weight_kg(raw.get("weight_kg_min")),
        "weight_kg_max": _normalize_weight_kg(raw.get("weight_kg_max")),
        "phase": _alias(raw, "phase", PHASE_ALIASES, VALID_PHASE),
        "severity": _alias(raw, "severity", SEVERITY_ALIASES, VALID_SEVERITY),
        "complication": _alias(raw, "complication", COMPLICATION_ALIASES, VALID_COMPLICATION),
        "category": _canonical_text(raw.get("category")),
    }
    if disease is None and raw_disease:
        result["disease_unresolved"] = str(raw_disease).strip()

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

# tambahan kode
_TIME_UNIT_WORDS = re.compile(r"\bjam\b|\bmenit\b|\bhari\b|\bminggu\b|\bbulan\b|\btahun\b", re.IGNORECASE)
_COUNT_UNIT_WORDS = re.compile(r"kali/hari|kali/minggu|x/hari|kali$|/hari$", re.IGNORECASE)


def _sanitize_claim_type(claim_type: str | None, unit: str | None) -> tuple[str | None, str | None]:
    """Perbaiki label claim_type yang tidak sinkron dengan unit-nya.
    Mengembalikan (claim_type_baru, alasan_dibuang_jika_ada)."""
    if unit is None:
        return claim_type, None

    u = unit.strip()

    if claim_type == "frequency" and _TIME_UNIT_WORDS.search(u) and not _COUNT_UNIT_WORDS.search(u):
        return "interval", None

    if claim_type == "interval" and not _TIME_UNIT_WORDS.search(u):
        return None, f"interval dengan unit non-waktu ('{u}')"

    if claim_type == "dose" and u == "%":
        return None, "'%' adalah konsentrasi formulasi, bukan dosis"

    return claim_type, None
# end of tambahan kode


def _parse_claim(raw: Any, condition: dict) -> dict | None:
    if not isinstance(raw, dict):
        return None

    claim_type = _normalize_claim_type(raw.get("claim_type"))
    if claim_type is None:
        return None

    medicine = _normalize_with_alias(raw.get("medicine"), PARAMETER_ALIASES, valid_set=VALID_MEDICINE, field_name="medicine")
    if not medicine:
        return None

    value_min = _to_float_or_none(raw.get("value_min"))
    value_max = _to_float_or_none(raw.get("value_max"))
    if value_min is not None and value_max is not None and value_min > value_max:
        return None
    if value_min == 0 and value_max == 0:
        return None

    unit_normalized = _normalize_unit(raw.get("unit"))

    # === TAMBAHAN: sanitasi claim_type vs unit ===
    claim_type, drop_reason = _sanitize_claim_type(claim_type, unit_normalized)
    if claim_type is None:
        logger.info("Klaim dibuang saat sanitasi: %s (medicine=%s)", drop_reason, medicine)
        return None
    # === akhir tambahan ===

    raw_prohibited = raw.get("prohibited")
    if isinstance(raw_prohibited, bool):
        prohibited = raw_prohibited
    elif claim_type == "contraindication":
        prohibited = True
    else:
        prohibited = None

    return _drop_none({
        "condition": condition,
        "claim_type": claim_type,
        "medicine": medicine,
        "value_min": value_min,
        "value_max": value_max,
        "unit": unit_normalized,
        "prohibited": prohibited,
    })


def _parse_entry(entry: dict) -> list[dict]:
    condition = _parse_condition(entry.get("condition"))
    if not condition or all(value is None for value in condition.values()):
        return []

    claim_raw = entry.get("claim") or []
    if not isinstance(claim_raw, list):
        return []

    return [
        claim
        for raw_claim in claim_raw
        if (claim := _parse_claim(raw_claim, condition)) is not None
    ]


def extract_claims(llm_json_output: str) -> list[dict]:
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
        return []

    all_claims = [
        claim
        for entry in entries
        if isinstance(entry, dict)
        for claim in _parse_entry(entry)
    ]

    logger.info("Total klaim berhasil diekstrak: %d", len(all_claims))
    return all_claims
