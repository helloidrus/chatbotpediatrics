"""
Decision layer for rule verification results.

Only confirmed violations trigger regeneration. Claims with no matching rule are
reported as warnings so the pipeline does not label unverifiable content as
fully compliant.
"""


def decide_action(verification_results):
    violations = [
        result for result in verification_results
        if result.get("status") == "violation"
    ]
    no_rule = [
        result for result in verification_results
        if result.get("status") == "no_rule"
    ]

    if violations:
        return {
            "action": "REGENERATE",
            "reason": "Guideline violations detected",
            "violations": violations,
            "warnings": no_rule,
        }

    if no_rule:
        return {
            "action": "PASS_WITH_WARNINGS",
            "reason": "No violations detected, but some claims had no matching rule",
            "warnings": no_rule,
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
