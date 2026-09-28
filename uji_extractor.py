import json
from pathlib import Path

from src.pipeline import Pipeline
from src.verification.claim_extractor import extract_claims
from src.verification.decision_layer import apply_decision
from src.verification.rule_engine import load_rules, verify_claims

pipeline = Pipeline()
rules_path = Path("data") / "rules" / "rule_pediatrics_nlm_bersih.json"
rules = load_rules(str(rules_path))

rag_text = """

Untuk neonatus < 1 minggu yang mengalami sepsis sekaligus meningitis, ampisilin diberikan **100 mg/kg secara intravena setiap 12 jam** (dosis ini berlaku untuk hari 1‑7; setelah hari 8 dosis diubah menjadi tiap 8 jam).

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
