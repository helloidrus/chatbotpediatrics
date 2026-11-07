import json
from pathlib import Path
from jsonschema import validate, ValidationError

# 1. Muat File Ontologi
RULES_DIR = Path(__file__).resolve().parents[2] / "data" / "rules"
with open(RULES_DIR / "normalization_dictionary.json", 'r', encoding='utf-8') as f:
    ontology = json.load(f)

# 2. Ekstrak Kunci Utama (Nilai Kanonikal Baku) dari Ontologi
valid_diseases = list(ontology['disease'].keys())
valid_phases = list(ontology['phase'].keys())
valid_severities = list(ontology['severity'].keys())
valid_complications = list(ontology['complication'].keys())
valid_claim_types = list(ontology['claim_type'].keys())
valid_medicines = list(ontology['medicine'].keys())
valid_units = list(ontology['unit'].keys())

# 3. Bangun Skema Validasi Dinamis (Menambahkan aturan 'enum')
rule_schema_semantic = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string"},
        "condition": {
            "type": "object",
            "properties": {
                # Wajib sesuai dengan 43 variasi
                "disease": {"type": "string", "enum": valid_diseases}, 
                
                # Boleh null (kosong), tapi jika ada isinya WAJIB sesuai ontologi
                "phase": {"type": ["string", "null"], "enum": valid_phases + [None]},
                "severity": {"type": ["string", "null"], "enum": valid_severities + [None]},
                "complication": {"type": ["string", "null"], "enum": valid_complications + [None]}
            },
            "required": ["disease"]
        },
        "claim": {
            "type": "object",
            "properties": {
                # Wajib sesuai dengan ontologi
                "claim_type": {"type": "string", "enum": valid_claim_types},
                "medicine": {"type": "string", "enum": valid_medicines},
                
                # Angka tidak di-enum karena nilainya dinamis
                "value_min": {"type": ["number", "null"]},
                "value_max": {"type": ["number", "null"]},
                
                # Boleh null, jika ada isi wajib sesuai ontologi
                "unit": {"type": ["string", "null"], "enum": valid_units + [None]}
            },
            "required": ["claim_type", "medicine"]
        },
        "metadata": {"type": "object"}
    },
    "required": ["rule_id", "condition", "claim", "metadata"]
}

# 4. Fungsi Uji Validasi Semantik
def hitung_semantic_validity(file_ai_bersih):
    with open(file_ai_bersih, 'r', encoding='utf-8') as f:
        data = json.load(f)
        ai_rules = data.get("rules", data)
        
    valid_count = 0
    error_logs = []

    for index, rule in enumerate(ai_rules):
        try:
            validate(instance=rule, schema=rule_schema_semantic)
            valid_count += 1
        except ValidationError as e:
            error_logs.append(f"Aturan {rule.get('rule_id', index)} Gagal Semantik: Atribut {e.json_path} bernilai '{e.instance}'. Info: {e.message}")

    total = len(ai_rules)
    print(f"Total Aturan Diuji: {total}")
    print(f"Total Valid Secara Semantik: {valid_count}")
    print(f"Semantic Validity Rate: {(valid_count/total)*100:.2f}%\n")
    
    if error_logs:
        print("--- SAMPEL ERROR ---")
        for log in error_logs[:10]:
            print(log)

# Jalankan validasi semantik pada basis aturan yang digunakan pipeline.
hitung_semantic_validity(RULES_DIR / "rule_base.json")