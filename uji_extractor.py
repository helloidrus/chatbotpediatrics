import json
from pathlib import Path

from src.pipeline import Pipeline
from src.verification.claim_extractor import extract_claims
from src.verification.decision_layer import apply_decision
from src.verification.rule_engine import load_rules, verify_claims

pipeline = Pipeline()
rules_path = Path("src") / "verification" / "rule_pediatrics.json"
rules = load_rules(str(rules_path))

rag_text = """

Dosis Ringer Laktat (RL) atau Ringer Asetat (RA) pada diare akut tergantung pada derajat dehidrasi. Berikut adalah pedoman dosis RL/RA pada diare akut:

- **Tanpa dehidrasi (kehilangan cairan <5% berat badan)**: tidak perlu diberikan RL/RA.
- **Mild dehidrasi (kehilangan cairan 5-10% berat badan)**: 50-100 mL/kgBB per hari, dibagi menjadi 4-6 dosis.
- **Moderate dehidrasi (kehilangan cairan 11-20% berat badan)**: 100-150 mL/kgBB per hari, dibagi menjadi 4-6 dosis.
- **Sedang berat dehidrasi (kehilangan cairan 21-30% berat badan)**: 150-200 mL/kgBB per hari, dibagi menjadi 4-6 dosis.
- **Berat dehidrasi (kehilangan cairan >30% berat badan)**: 200-250 mL/kgBB per hari, dibagi menjadi 4-6 dosis.

Namun, perlu diingat bahwa pedoman di atas hanya sebagai acuan dan dapat disesuaikan dengan kebutuhan pas

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
