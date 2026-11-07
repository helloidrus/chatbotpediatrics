import json
import re
import os
from pathlib import Path

# ==========================================
# 1. FUNGSI NORMALISASI TEKS (ANTI-ERROR)
# ==========================================
def normalize_text(text):
    """
    Mengubah teks menjadi huruf kecil dan menghancurkan semua 
    spasi berlebih, enter, atau tab yang tersembunyi dari output AI.
    """
    if text is None:
        return ""
    text_str = str(text).lower()
    # Mengganti karakter whitespace apa pun (\n, \t, \xa0, spasi ganda) menjadi 1 spasi
    return re.sub(r'\s+', ' ', text_str).strip()

# ==========================================
# 2. FUNGSI PEMETAAN ONTOLOGI (CANONICAL MAPPER)
# ==========================================
def get_canonical_value(category, raw_value, ontology):
    """
    Mencari nilai baku berdasarkan array sinonim di ontology.json
    """
    # Jika nilai kosong atau kategori tidak ada di ontologi, biarkan apa adanya
    if not raw_value or category not in ontology:
        return raw_value
    
    # Bersihkan nilai mentah dari AI secara agresif
    raw_clean = normalize_text(raw_value)
    
    # Lakukan pencarian di dalam ontologi
    for canonical_key, synonyms in ontology[category].items():
        # Bersihkan array sinonim sebelum dicocokkan
        synonyms_clean = [normalize_text(s) for s in synonyms]
        canonical_clean = normalize_text(canonical_key)
        
        # Jika nilai AI cocok dengan salah satu isi array atau key utamanya
        if raw_clean in synonyms_clean or raw_clean == canonical_clean:
            return canonical_key # Kembalikan nama standarnya (canonical)
            
    # JIKA TIDAK KETEMU: Print log error ke terminal agar mudah dilacak
    print(f"⚠️ BOCOR [Kategori: {category}]: Nilai '{raw_value}' tidak ada di array ontologi.")
    return raw_value

# ==========================================
# 3. PIPELINE UTAMA PEMBERSIHAN
# ==========================================
def clean_ai_rules(raw_rules_file, ontology_file, output_file):
    print("Memulai proses Canonical Entity Mapping...\n")
    
    # Buka dan baca file Ontologi
    with open(ontology_file, 'r', encoding='utf-8-sig') as f:
        ontology = json.load(f)
        
    # Buka dan baca file AI Mentah
    with open(raw_rules_file, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)
        # Ambil list aturan, antisipasi apakah format json diawali object "rules" atau langsung array
        ai_rules = data.get("rules", data) if isinstance(data, dict) else data

    cleaned_rules = []
    
    # Iterasi untuk setiap aturan
    for rule in ai_rules:
        # Ambil blok condition dan claim (gunakan dict kosong jika tidak ada)
        cond = rule.get("condition", {})
        claim = rule.get("claim", {})
        
        # ----------------------------------------------------
        # CANONICAL ENTITY MAPPING (Pencocokan dengan Ontologi)
        # ----------------------------------------------------
        # Normalisasi blok Condition
        if cond.get("disease"):
            cond["disease"] = get_canonical_value("disease", cond.get("disease"), ontology)
        if cond.get("phase"):
            cond["phase"] = get_canonical_value("phase", cond.get("phase"), ontology)
        if cond.get("severity"):
            cond["severity"] = get_canonical_value("severity", cond.get("severity"), ontology)
        if cond.get("complication"):
            cond["complication"] = get_canonical_value("complication", cond.get("complication"), ontology)
            
        # Normalisasi blok Claim
        if claim.get("claim_type"):
            claim["claim_type"] = get_canonical_value("claim_type", claim.get("claim_type"), ontology)
        if claim.get("medicine"):
            claim["medicine"] = get_canonical_value("medicine", claim.get("medicine"), ontology)
        if claim.get("unit"):
            claim["unit"] = get_canonical_value("unit", claim.get("unit"), ontology)

        # Simpan kembali ke dalam rule
        rule["condition"] = cond
        rule["claim"] = claim
        cleaned_rules.append(rule)

    # ----------------------------------------------------
    # 4. EKSPOR HASIL BERSIH KE JSON BARU
    # ----------------------------------------------------
    output_data = {"rules": cleaned_rules}
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Selesai! {len(cleaned_rules)} aturan telah dipetakan ke nilai baku.")
    print(f"📁 Hasil disimpan di: {output_file}")

# ==========================================
# EKSEKUSI SCRIPT
# ==========================================
if __name__ == "__main__":
    RULES_DIR = Path(__file__).resolve().parents[2] / "data" / "rules"
    FILE_MENTAH = RULES_DIR / "rule_pediatrics_nlm.json"
    FILE_ONTOLOGI = RULES_DIR / "normalization_dictionary.json"
    FILE_BERSIH = RULES_DIR / "rule_pediatrics_nlm_bersih.json"
    
    if os.path.exists(FILE_MENTAH) and os.path.exists(FILE_ONTOLOGI):
        clean_ai_rules(FILE_MENTAH, FILE_ONTOLOGI, FILE_BERSIH)
    else:
        print("❌ ERROR: File mentah atau ontologi tidak ditemukan di folder ini.")