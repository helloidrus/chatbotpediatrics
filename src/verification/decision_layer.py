# -----------------------------------
# DECISION LAYER
# -----------------------------------

def decide_action(verification_results):

    violations = [
        r for r in verification_results
        if r.get("status") == "violation"
    ]

    if not violations:
        return {
            "action": "PASS",
            "reason": "All claims comply with clinical guideline"
        }

    return {
        "action": "REGENERATE",
        "reason": "Guideline violations detected",
        "violations": violations
    }


def apply_decision(original_answer, verification_results, generator):

    decision = decide_action(verification_results)

    if decision["action"] == "REGENERATE":
        verified_response = generator.regenerate_answer(
            original_answer,
            decision["violations"]
        )
        return verified_response, decision

    return original_answer, decision
