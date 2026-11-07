import json
from pathlib import Path

from src.pipeline import Pipeline
from src.verification.claim_extractor import extract_claims
from src.verification.decision_layer import apply_decision
from src.verification.rule_engine import load_rules, verify_claims

ROOT_DIR = Path(__file__).resolve().parents[2]

pipeline = Pipeline()
rules_path = ROOT_DIR / "data" / "rules" / "rule_base.json"
rules = load_rules(str(rules_path))

rag_text = """

Untuk anak yang mengalami angioedema berat atau anafilaksis, epinefrin (adrenalin) 1 : 1000 diberikan secara intramuskular dengan dosis **0,01 mg per kilogram berat badan** (setara dengan 0,1 mL per kg karena larutan 1 mg/mL). Dosis maksimum satu kali suntikan adalah **0,3 mg (0,3 mL)** pada anak ≤30 kg, atau **0,5 mg (0,5 mL)** bila berat badan >30 kg. Jika tidak ada respons klinis, dosis dapat diulang setiap 5‑10 menit dengan batas total yang sama.

"""

claim_extraction = pipeline.generator.generate_claim_extraction(rag_text)
claim_doc = extract_claims(claim_extraction)
violations = verify_claims(claim_doc, rules)
rag_text_verified, decision = apply_decision(
    original_answer=rag_text,
    verification_results=violations,
    generator=pipeline.generator,
)

print("\n--- CLAIM RAW ---")
print(claim_extraction)
print("\n--- CLAIM NORMALIZED ---")
print(json.dumps(claim_doc, indent=2, ensure_ascii=False))
print("\n--- RULE ENGINE ---")
print(json.dumps(violations, indent=2, ensure_ascii=False)) 
print("\n--- DECISION ---")
print(json.dumps(decision, indent=2, ensure_ascii=False))
print("\n--- RAG TEXT VERIFIED ---")
print(rag_text_verified)
