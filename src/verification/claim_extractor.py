import json
import re

EMPTY_CLAIM = {
    "condition": {"age_months": None, "weight_kg": None, "disease": None},
    "claims": [],
}

DISEASE_MAP = {
    "malaria": "malaria",
    "malaria tanpa komplikasi": "malaria",
    "malaria uncomplicated": "malaria",
    "malaria ringan": "malaria",
    "malaria berat": "malaria berat",
    "severe malaria": "malaria berat",
    "malaria falciparum berat": "malaria berat",
    "malaria falciparum": "malaria falciparum",
    "plasmodium falciparum": "malaria falciparum",
    "p falciparum": "malaria falciparum",
    "p. falciparum": "malaria falciparum",
    "malaria falciparum resisten klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "malaria falciparum resisten terhadap klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "plasmodium falciparum resisten klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "plasmodium falciparum yang resisten terhadap klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "p falciparum resisten klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "p. falciparum resisten klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "p falciparum yang resisten terhadap klorokuin": "p. falciparum yang resisten terhadap klorokuin",
    "malaria vivax": "malaria vivax, malariae, dan ovale",
    "plasmodium vivax": "malaria vivax, malariae, dan ovale",
    "p vivax": "malaria vivax, malariae, dan ovale",
    "p. vivax": "malaria vivax, malariae, dan ovale",
    "malaria malariae": "malaria vivax, malariae, dan ovale",
    "plasmodium malariae": "malaria vivax, malariae, dan ovale",
    "p malariae": "malaria vivax, malariae, dan ovale",
    "p. malariae": "malaria vivax, malariae, dan ovale",
    "malaria ovale": "malaria vivax, malariae, dan ovale",
    "plasmodium ovale": "malaria vivax, malariae, dan ovale",
    "p ovale": "malaria vivax, malariae, dan ovale",
    "p. ovale": "malaria vivax, malariae, dan ovale",
    "malaria vivax, malariae, dan ovale": "malaria vivax, malariae, dan ovale",
}

CLAIM_TYPES = {"dose", "frequency", "duration"}

PARAMETER_MAP = {
    "klorokuin": "klorokuin sulfat",
    "chloroquine": "klorokuin sulfat",
    "chloroquine sulfate": "klorokuin sulfat",
    "klorokuin sulfat": "klorokuin sulfat",
    "kina": "kina dihidroklorid",
    "kina dihidroklorida": "kina dihidroklorid",
    "kina dihidroklorid": "kina dihidroklorid",
    "quinine dihydrochloride": "kina dihidroklorid",
    "kuinin": "kuinin sulfat",
    "quinine": "kuinin sulfat",
    "quinine sulfate": "kuinin sulfat",
    "kuinin sulfat": "kuinin sulfat",
    "tetrasiklin": "tetrasiklin",
    "tetracycline": "tetrasiklin",
    "primakuin": "primakuin fosfat",
    "primaquine": "primakuin fosfat",
    "primaquine phosphate": "primakuin fosfat",
    "primakuin fosfat": "primakuin fosfat",
}

UNIT_MAP = {
    "mg per kg": "mg/kg",
    "mg/kg bb": "mg/kg",
    "mg/kgbb": "mg/kg",
    "mg per kg bb": "mg/kg",
    "mg per kilogram": "mg/kg",
    "mg/kg berat badan": "mg/kg",
    "mg/kg/hari": "mg/kg/day",
    "mg/kgbb/hari": "mg/kg/day",
    "mg/kgbb/hr": "mg/kg/day",
    "mg/kgbb per hari": "mg/kg/day",
    "mg per kg per hari": "mg/kg/day",
    "mg/kg bb/hari": "mg/kg/day",
    "mg/kg bb per hari": "mg/kg/day",
    "mg/kg/day": "mg/kg/day",
    "mg/kg/dosis": "mg/kg/dose",
    "mg/kg bb/dosis": "mg/kg/dose",
    "mg/kgbb/dosis": "mg/kg/dose",
    "mg per kg per dosis": "mg/kg/dose",
    "mg per kg tiap dosis": "mg/kg/dose",
    "mg/kg dose": "mg/kg/dose",
    "mg/kg per dose": "mg/kg/dose",
    "mg garam/kg/dosis": "mg_garam/kg/dose",
    "mg garam/kg/dose": "mg_garam/kg/dose",
    "mg garam per kg per dosis": "mg_garam/kg/dose",
    "mg garam per kg tiap dosis": "mg_garam/kg/dose",
    "mg basa/kg": "mg_basa/kg",
    "mg basa per kg": "mg_basa/kg",
    "mg basa/kg bb": "mg_basa/kg",
    "mg basa/kgbb": "mg_basa/kg",
    "mg/kg total dosis": "mg/kg_total_dose",
    "mg/kg total dose": "mg/kg_total_dose",
    "mg/kg bb total dosis": "mg/kg_total_dose",
    "mg/kg bb total dose": "mg/kg_total_dose",
    "mg/kgbb total dosis": "mg/kg_total_dose",
    "mg/kgbb total dose": "mg/kg_total_dose",
    "mg total/kg": "mg/kg_total_dose",
    "mg per kg total dosis": "mg/kg_total_dose",
    "mg per kg total dose": "mg/kg_total_dose",
    "kali per hari": "times/day",
    "kali sehari": "times/day",
    "kali / hari": "times/day",
    "x per hari": "times/day",
    "x/hari": "times/day",
    "x / hari": "times/day",
    "dd": "times/day",
    "times/day": "times/day",
    "jam": "hours",
    "hour": "hours",
    "hours": "hours",
    "hari": "days",
    "day": "days",
    "days": "days",
}

# Metode untuk mengekstrak klaim dari teks jawaban
def _extract_json_object(text):
    if not text:
        return None

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None

# Metode parsing condition dari JSON mentah
def parse_condition(raw_condition):
    if not isinstance(raw_condition, dict):
        return {}

    return {
        "disease": raw_condition.get("disease"),
        "age_months": raw_condition.get("age_months"),
        "weight_kg": raw_condition.get("weight_kg"),
    }

# Metode parsing klaim dari JSON mentah
def parse_claim(raw_claim):
    if not isinstance(raw_claim, dict):
        return None

    return {
        "claim_type": raw_claim.get("claim_type"),
        "parameter": raw_claim.get("parameter"),
        "value_min": raw_claim.get("value_min"),
        "value_max": raw_claim.get("value_max"),
        "unit": raw_claim.get("unit"),
        "evidence_text": raw_claim.get("evidence_text"),
    }

# Metode untuk parsing dokumen klaim lengkap dari teks jawaban
def parse_claim_document(text):
    data = _extract_json_object(text)
    if not isinstance(data, dict):
        return None

    raw_claims = data.get("claims")
    parsed_claims = []
    if isinstance(raw_claims, list):
        parsed_claims = [claim for item in raw_claims if (claim := parse_claim(item))]

    return {
        "condition": parse_condition(data.get("condition")),
        "claims": parsed_claims,
    }
 
# End of parsing methods



# Metode normalisasi string
def _norm_str(value):
    return str(value).lower().strip() if value else None

# Metode normalisasi nilai numerik
def _norm_float(value):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = float(value.strip().replace(",", "."))
        else:
            value = float(value)
        return int(value) if value.is_integer() else value
    except (TypeError, ValueError):
        return None

# Metode normalisasi usia dalam bulan
def _norm_age_months(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(tahun|th|bulan|bln)?", str(value).lower())
    if not match:
        return None

    amount = float(match.group(1).replace(",", "."))
    unit = match.group(2)
    return int(amount * 12) if unit in {"tahun", "th"} else int(amount)

# Metode normalisasi nama penyakit
def normalize_disease(raw_disease):
    disease = _norm_str(raw_disease)
    if not disease:
        return None
    return DISEASE_MAP.get(disease, disease)

# Metode normalisasi nama parameter obat
def normalize_parameter(raw_parameter):
    parameter = _norm_str(raw_parameter)
    if not parameter:
        return None
    parameter = re.sub(r"\b(iv|oral|po|injeksi|infus)\b", "", parameter).strip()
    return PARAMETER_MAP.get(parameter, parameter)

# Metode normalisasi kondisi klinis
def normalize_condition(parsed_condition):
    return {
        "disease": normalize_disease(parsed_condition.get("disease")),
        "age_months": _norm_age_months(parsed_condition.get("age_months")),
        "weight_kg": _norm_float(parsed_condition.get("weight_kg")),
    }

# Metode normalisasi klaim
def normalize_claim(parsed_claim):
    claim_type = _norm_str(parsed_claim.get("claim_type"))
    parameter = normalize_parameter(parsed_claim.get("parameter"))
    value_min = _norm_float(parsed_claim.get("value_min"))
    value_max = _norm_float(parsed_claim.get("value_max"))
    unit = UNIT_MAP.get(_norm_str(parsed_claim.get("unit")), _norm_str(parsed_claim.get("unit")))
    evidence_text = parsed_claim.get("evidence_text")

    if claim_type not in CLAIM_TYPES:
        return None
    if value_min is None and value_max is None:
        return None
    if unit is None:
        return None
    if claim_type == "dose" and not parameter:
        return None

    if value_min is None:
        value_min = value_max
    if value_max is None:
        value_max = value_min

    normalized_claim = {
        "claim_type": claim_type,
        "parameter": parameter,
        "constraint": {
            "min": value_min,
            "max": value_max,
            "unit": unit,
        },
    }
    if evidence_text:
        normalized_claim["evidence_text"] = evidence_text
    return normalized_claim

# End of normalization methods



# Metode utama untuk mengekstrak dan menormalisasi klaim dari teks jawaban LLM
def extract_claims(text):
    parsed_document = parse_claim_document(text)
    if not parsed_document:
        return EMPTY_CLAIM.copy()

    return {
        "condition": normalize_condition(parsed_document["condition"]),
        "claims": [
            normalized_claim
            for claim in parsed_document["claims"]
            if (normalized_claim := normalize_claim(claim))
        ],
    }
