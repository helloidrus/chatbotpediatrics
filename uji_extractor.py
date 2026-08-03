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

"Obat malaria anak Anda harus diminum selama 14 hari karena beberapa alasan:

Pertama, malaria adalah penyakit yang kompleks dan memerlukan waktu yang lama untuk diobati. Selain itu, parasit malaria dapat bersembunyi di dalam tubuh dan memerlukan waktu yang lama untuk dihancurkan oleh obat.

Kedua, obat malaria yang digunakan, seperti klorokuin dan kina, memerlukan waktu yang lama untuk mencapai konsentrasi yang efektif di dalam tubuh. Jika obat hanya diminum selama beberapa hari, maka konsentrasinya mungkin tidak cukup untuk menghancurkan parasit malaria secara efektif.

Ketiga, malaria dapat menyebabkan komplikasi yang serius, seperti malaria serebral, anemia berat, dan gagal ginjal. Oleh karena itu, obat malaria harus diminum selama 14 hari untuk memastikan bahwa parasit malaria dihancurkan secara efektif dan komplikasi dapat dicegah.

Jadi, untuk memastikan bahwa anak Anda sembuh dari malaria secara efektif, obat harus diminum selama 14 hari."


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
