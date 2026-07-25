import unittest

from src.verification.claim_extractor import extract_claims
from src.verification.rule_engine import verify_claims


class RuleEngineSpecificityTest(unittest.TestCase):
    def test_prefers_severity_specific_rule_over_generic_rule(self) -> None:
        claim = {
            "claim_type": "duration",
            "medicine": "rifampisin",
            "value_min": 8,
            "value_max": 8,
            "unit": "bulan",
            "condition": {
                "disease": "tuberkulosis",
                "phase": "continuation",
                "severity": "berat",
            },
        }

        rules = [
            {
                "rule_id": "tuberkulosis_duration_22",
                "condition": {
                    "disease": "tuberkulosis",
                    "phase": "continuation",
                },
                "claim": {
                    "claim_type": "duration",
                    "medicine": "rifampisin",
                    "value_min": 4,
                    "value_max": 4,
                    "unit": "bulan",
                },
            },
            {
                "rule_id": "tuberkulosis_duration_222",
                "condition": {
                    "disease": "tuberkulosis",
                    "phase": "continuation",
                    "severity": "berat",
                },
                "claim": {
                    "claim_type": "duration",
                    "medicine": "rifampisin",
                    "value_min": 7,
                    "value_max": 10,
                    "unit": "bulan",
                },
            },
        ]

        result = verify_claims([claim], rules)[0]

        self.assertEqual(result["status"], "compliant")
        self.assertEqual(result["rule_id"], "tuberkulosis_duration_222")

    def test_normalizes_unit_with_age_suffix_to_ontology_canonical(self) -> None:
        llm_output = (
            '{"entries": [{"condition": {"disease": "konstipasi", "age_month_min": 0, '
            '"age_month_max": 12}, "claim": [{"claim_type": "dose", "medicine": '
            '"mineral_oil", "value_min": 15, "value_max": 30, "unit": "ml/tahun umur"}]}]}'
        )

        claims = extract_claims(llm_output)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["unit"], "mL/tahun")

    def test_preserves_explicit_false_for_contraindication(self) -> None:
        llm_output = (
            '{"entries": [{"condition": {"disease": "pneumonia"}, '
            '"claim": [{"claim_type": "contraindication", "medicine": "ampisilin", '
            '"prohibited": false}]}]}'
        )

        claims = extract_claims(llm_output)

        self.assertEqual(len(claims), 1)
        self.assertFalse(claims[0]["prohibited"])

    def test_drops_claims_with_zero_only_value_range(self) -> None:
        llm_output = (
            '{"entries": [{"condition": {"disease": "pneumonia"}, '
            '"claim": [{"claim_type": "contraindication", "medicine": "ampisilin", '
            '"value_min": 0, "value_max": 0}]}]}'
        )

        claims = extract_claims(llm_output)

        self.assertEqual(claims, [])


if __name__ == "__main__":
    unittest.main()
