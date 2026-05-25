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
    warnings = [
        result for result in verification_results
        if result.get("status") in {"uncovered", "no_rule"}
    ]

    if violations:
        return {
            "action": "REGENERATE",
            "reason": "Guideline violations detected",
            "violations": violations,
            "warnings": warnings,
        }

    if warnings:
        return {
            "action": "PASS_WITH_WARNINGS",
            "reason": "No violations detected, but some claims are outside rule coverage",
            "warnings": warnings,
        }

    if not verification_results:
        return {
            "action": "PASS_WITH_WARNINGS",
            "reason": "No verifiable clinical claims were extracted",
            "warnings": [],
        }

    return {
        "action": "PASS",
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
