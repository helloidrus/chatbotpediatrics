import json
from pathlib import Path

from src.pipeline import Pipeline
from src.verification.claim_extractor import extract_claims
from src.verification.decision_layer import apply_decision
from src.verification.rule_engine import load_rules, verify_claims

pipeline = Pipeline()
rules_path = Path("data") / "rules" / "rule_pediatrics.json"
rules = load_rules(str(rules_path))

rag_text = """
Dosis adrenalin 1:1000 untuk anak dengan angioedema berat atau anafilaksis adalah 0,01 mg/kg (setara 0,01 mL/kg dari larutan 1 mg/mL).


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
