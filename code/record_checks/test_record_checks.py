"""Tests for source preservation and cross-field checks in the proposed contract."""
import copy
import json
import unittest
from pathlib import Path

from check_screening_record import check_record


class RecordChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.schema = json.loads((root / "specifications/screening_record.schema.json").read_text())
        cls.observed = json.loads((root / "specifications/observed_H_1_6_3.json").read_text())

    def test_observed_record_preserves_screening_authority_and_receiving_context(self):
        result = check_record(self.observed, self.schema)
        self.assertTrue(result["format_valid"])
        self.assertEqual(result["application_issues"], [])
        self.assertIsNone(self.observed["source"]["component"])
        self.assertEqual(self.observed["mapping_context"]["receiving_component"], "Buffer")
        self.assertEqual(self.observed["screening"]["authorities"],
                         ["Allan Hedin", "Johan Andersson", "Kristina Skagius"])
        self.assertEqual(self.observed["adoption"]["status"], "unrecorded")
        self.assertEqual(len(self.observed["relations"]), 2)
        self.assertTrue(any(x["code"] == "review.scope" for x in result["technical_review_tasks"]))

    def test_format_failure_is_separate_from_application_failure(self):
        malformed = copy.deepcopy(self.observed)
        malformed["relations"][0]["targets"] = "Bu13"
        result = check_record(malformed, self.schema)
        self.assertFalse(result["format_valid"])
        self.assertEqual(result["application_issues"], [])
        record = copy.deepcopy(self.observed)
        record["adoption"] = {"status": "recorded", "authority": "Illustrative reviewer",
                              "decision_date": "2026-10-10", "adopted_relation_ids": ["absent"],
                              "justification": "Illustrative cross-field check."}
        result = check_record(record, self.schema)
        self.assertTrue(result["format_valid"])
        self.assertEqual(result["application_issues"][0]["code"], "application.adoption_reference")

    def test_recorded_adoption_requires_target_and_specified_scope(self):
        record = copy.deepcopy(self.observed)
        relation = record["relations"][0]
        relation["targets"] = []
        record["adoption"] = {"status": "recorded", "authority": "Illustrative reviewer",
                              "decision_date": "2026-10-10", "adopted_relation_ids": [relation["relation_id"]],
                              "justification": "Illustrative cross-field check."}
        result = check_record(record, self.schema)
        self.assertTrue(result["format_valid"])
        codes = {x["code"] for x in result["application_issues"]}
        self.assertEqual(codes, {"application.adopted_target", "application.adopted_scope"})

    def test_retrieval_lead_cannot_exceed_eligible_pool(self):
        record = copy.deepcopy(self.observed)
        record["retrieval_leads"] = [{"candidate": copy.deepcopy(record["relations"][0]["targets"][0]),
                                      "origin": "analytical_retrieval", "method_id": "illustrative",
                                      "rank": 2, "score": 0.2, "threshold": None, "eligible_pool_size": 1,
                                      "missing_source_fields": [], "query_fingerprint": "illustrative"}]
        result = check_record(record, self.schema)
        self.assertTrue(result["format_valid"])
        self.assertIn("application.retrieval_rank", {x["code"] for x in result["application_issues"]})


if __name__ == "__main__":
    unittest.main()
