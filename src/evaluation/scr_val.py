import json
from pathlib import Path
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# 1. Definisi Skema Berdasarkan Struktur Target
rule_schema = {
    "type": "object",
    "properties": {
        "rule_id": {"type": "string"},
        "condition": {
            "type": "object",
            "properties": {
                "disease": {"type": ["string", "null"]},
                "age_month_min": {"type": ["number", "null"]}, # number mencakup float
                "age_month_max": {"type": ["number", "null"]},
                "weight_kg_min": {"type": ["number", "null"]},
                "weight_kg_max": {"type": ["number", "null"]},
                "phase": {"type": ["string", "null"]},
                "severity": {"type": ["string", "null"]},
                "complication": {"type": ["string", "null"]}
            },
            "required": ["disease"]
        },
        "claim": {
            "type": "object",
            "properties": {
                "claim_type": {"type": "string"},
                "medicine": {"type": "string"},
                "value_min": {"type": ["number", "null"]},
                "value_max": {"type": ["number", "null"]},
                "unit": {"type": ["string", "null"]}
            },
            "required": ["claim_type", "medicine"]
        },
        "metadata": {
            "type": "object",
            "properties": {
                "source": {"type": ["string", "null"]},
                "section": {"type": ["string", "null"]},
                "page": {"type": ["integer", "null"]}, # integer khusus bilangan bulat
                "text": {"type": ["string", "null"]}
            }
        }
    },
    "required": ["rule_id", "condition", "claim", "metadata"]
}

# 2. Proses Validasi
def hitung_scr(file_path):
    try:
        # UBAH ENCODING MENJADI 'utf-8-sig' DI BARIS INI
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            data = json.load(f) # Validasi sintaks dasar otomatis di sini
            
            # Jika file diawali dengan "rules": [ ... ]
            if isinstance(data, dict) and "rules" in data:
                ai_rules = data["rules"]
            else:
                ai_rules = data
                
    except json.JSONDecodeError as e:
        print(f"GAGAL TOTAL: File JSON tidak valid secara sintaks dasar. Error: {e}")
        return

    valid_count = 0
    error_logs = []

    for index, rule in enumerate(ai_rules):
        try:
            validate(instance=rule, schema=rule_schema)
            valid_count += 1
        except ValidationError as e:
            # Mencatat lokasi persis dan alasan error
            error_logs.append(f"Aturan {rule.get('rule_id', f'Index {index}')} Error: {e.message}")

    # 3. Kalkulasi dan Laporan SCR
    total_rules = len(ai_rules)
    if total_rules == 0:
        print("File JSON kosong atau tidak berisi daftar aturan.")
        return

    scr_score = (valid_count / total_rules) * 100

    print(f"Total Aturan Diekstrak AI: {total_rules}")
    print(f"Total Aturan Valid Sesuai Skema: {valid_count}")
    print(f"Schema Conformance Rate (SCR): {scr_score:.2f}%\n")
    
    
    if error_logs:
        print("--- SAMPEL ERROR LOGS ---")
        for log in error_logs[:10]: # Tampilkan 10 error pertama
            print(log)

# Jalankan skrip pada file hasil ekstraksi AI Anda
# hitung_scr('rule_pediatrics_ai.json')
hitung_scr(Path(__file__).resolve().parents[2] / "data" / "rules" / "rule_base.json")