from pathlib import Path

from src.llm.generator import Generator
from src.verification.claim_extractor import extract_claims
from src.verification.rule_engine import load_rules, verify_claims


def _count_status(verifications, status):
    return sum(1 for item in verifications if item.get("status") == status)


def _safe_ratio(numerator, denominator):
    if denominator == 0:
        return 0.0
    return numerator / denominator


def evaluate_response(response_text, generator, rules):
    claim_extraction = generator.generate_claim_extraction(response_text)
    claim_doc = extract_claims(claim_extraction)
    verifications = verify_claims(claim_doc, rules)

    total_claims = len(claim_doc.get("claims", []))
    matched_claims = len(verifications)
    passed_claims = _count_status(verifications, "pass")
    violated_claims = _count_status(verifications, "violation")
    unmatched_claims = max(total_claims - matched_claims, 0)

    return {
        "response_text": response_text,
        "claim_extraction": claim_extraction,
        "claim_doc": claim_doc,
        "verifications": verifications,
        "metrics": {
            "total_claims": total_claims,
            "matched_claims": matched_claims,
            "passed_claims": passed_claims,
            "violated_claims": violated_claims,
            "unmatched_claims": unmatched_claims,
            "adherence": _safe_ratio(passed_claims, matched_claims),
            "violation_rate": _safe_ratio(violated_claims, matched_claims),
            # Proxy hallucination: claims extracted from response but not covered by any rule.
            "hallucination_rate": _safe_ratio(unmatched_claims, total_claims),
        },
    }


def evaluate_pipeline_result(pipeline_result, generator=None, rules=None, rules_path=None):
    if generator is None:
        generator = Generator()

    if rules is None:
        if rules_path is None:
            rules_path = Path(__file__).resolve().parent.parent / "verification" / "rule_pediatrics.json"
        rules = load_rules(str(rules_path))

    responses = {
        "llm": pipeline_result["llm_response"],
        "rag": pipeline_result["rag_response"],
        "rag_rule": pipeline_result["verified_response"],
    }

    return {
        model_name: evaluate_response(response_text, generator, rules)
        for model_name, response_text in responses.items()
    }


def summarize_evaluation(evaluation_result):
    summary = {}

    for model_name, result in evaluation_result.items():
        metrics = result["metrics"]
        summary[model_name] = {
            "hallucination_rate": metrics["hallucination_rate"],
            "adherence": metrics["adherence"],
            "violation_rate": metrics["violation_rate"],
            "total_claims": metrics["total_claims"],
            "matched_claims": metrics["matched_claims"],
            "violated_claims": metrics["violated_claims"],
        }

    return summary
