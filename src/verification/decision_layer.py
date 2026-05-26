"""
Decision layer for rule verification results.

Only confirmed violations trigger regeneration. Claims outside the current rule
coverage are reported as warnings so the pipeline does not label unverifiable
content as fully compliant.
"""


def decide_action(verification_results):
    violations = [
        result for result in verification_results
        if result.get("status") == "violation"
    ]
    uncovered = [
        result for result in verification_results
        if result.get("status") == "uncovered"
    ]
    no_rule = [
        result for result in verification_results
        if result.get("status") == "no_rule"
    ]
    warnings = uncovered + no_rule

    total = len(verification_results)
    covered = total - len(uncovered) - len(no_rule)
    base = {
        "coverage_rate": round(covered / total, 3) if total > 0 else 0.0,
        "total_claims": total,
        "verified_claims": covered,
    }

    if violations:
        return {
            "action": "REGENERATE",
            **base,
            "reason": "Guideline violations detected",
            "violations": violations,
            "warnings": warnings,
        }

    if warnings:
        return {
            "action": "PASS_WITH_WARNINGS",
            **base,
            "reason": "No violations detected, but some claims are outside rule coverage",
            "warnings": warnings,
        }

    if not verification_results:
        return {
            "action": "NO_CLAIMS_EXTRACTED",
            **base,
            "reason": "No verifiable clinical claims were extracted",
            "warnings": [],
        }

    return {
        "action": "PASS",
        **base,
        "reason": "All extracted claims comply with clinical guideline",
        "warnings": [],
    }


def apply_decision(original_answer, verification_results, generator):
    decision = decide_action(verification_results)

    if decision["action"] == "REGENERATE":
        verified_response = generator.regenerate_answer(
            original_answer,
            decision["violations"],
        )
        return verified_response, decision

    return original_answer, decision
