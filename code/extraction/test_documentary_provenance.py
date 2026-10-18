"""Scientific regression checks for contextual documentary-reference extraction.

Run: python -m unittest discover -s code/extraction -p 'test_*.py'
"""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_covered_elsewhere_audit import build, numeric_key, SOURCE_SNAPSHOT, RULES


class DocumentaryProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(SOURCE_SNAPSHOT.read_text())
        cls.rules = json.loads(RULES.read_text())
        records, cls.relations = build(cls.snapshot, cls.rules)
        cls.records = records.set_index("pfep_id")

    def relations_for(self, pid):
        return self.relations[self.relations.source_pfep_id.eq(pid)]

    def test_complete_cohort_including_empty_sources(self):
        self.assertEqual(len(self.records), 200)
        self.assertEqual(self.records.index.nunique(), 200)
        n = self.records[self.records.project_letter.eq("N")]
        self.assertEqual(len(n), 145)
        self.assertEqual(int(n.imported_text_present.sum()), 1)
        self.assertEqual(int(n.skb_explanatory_rationale_present.sum()), 0)
        self.assertEqual(int(n.n_relations.sum()), 0)
        self.assertTrue(n.documentary_unresolved.eq(1).all())

    def test_decimal_quantities_are_not_reference_identifiers(self):
        row = self.relations_for("W 2.072")
        targets = set(row.loc[row.target_type.eq("PFEP"), "target_id"])
        self.assertEqual(targets, {"W 2.030", "W 2.043", "W 2.044", "W 2.049", "W 2.093"})
        self.assertFalse(targets & {"W 1.001", "W 1.004", "W 1.005", "W 3.006"})
        self.assertEqual(int(row.benchmark_eligible.sum()), 0)  # related discussion, not a treatment assignment

    def test_integer_local_identifiers_and_namespace(self):
        row = self.relations_for("I 165")
        self.assertEqual(set(row.target_id), {"I 058", "I 061", "I 126", "I 273"})
        self.assertTrue(row.benchmark_eligible.eq(1).all())
        self.assertTrue(row.target_exists_in_stage.eq("yes").all())
        self.assertEqual(numeric_key("I 058"), numeric_key("I 58"))

    def test_exclusion_object_is_not_coverage_destination(self):
        row = self.relations_for("J 2.3.02")
        gold = set(row.loc[row.benchmark_eligible.eq(1), "target_id"])
        self.assertEqual(gold, {"J 2.1.01"})
        exclusion = row[row.target_id.eq("J 2.3.03")].iloc[0]
        self.assertEqual(exclusion.relation_semantics, "other_record_exclusion")
        self.assertEqual(exclusion.direction_valid, 0)
        self.assertEqual(exclusion.explicit_destination, 0)

    def test_causal_references_preserve_direction_and_are_not_gold(self):
        causes = self.relations_for("J 4.2.05")
        self.assertGreater(len(causes), 20)
        self.assertTrue(causes.relation_semantics.eq("target_causes_source").all())
        self.assertTrue(causes.relation_direction.eq("target_to_source").all())
        self.assertEqual(int(causes.benchmark_eligible.sum()), 0)
        effects = self.relations_for("J 5.19")
        self.assertTrue(effects.relation_semantics.eq("source_causes_target").all())
        self.assertEqual(int(effects.benchmark_eligible.sum()), 0)

    def test_unqualified_duplicate_titles_remain_ambiguous(self):
        row = self.relations_for("A 1.39")
        glaciation = row[row.target_literal.eq("Glaciation")]
        self.assertEqual(set(glaciation.target_id), {"A 1.38", "A 2.30", "A 3.057"})
        self.assertTrue(glaciation.ambiguity.eq("multiple_source_inventory_records").all())
        self.assertTrue(glaciation.reference_verified.eq(0).all())
        climate = row[row.target_literal.eq("Climate change")]
        self.assertEqual(set(climate.target_id), {"A 2.07", "A 3.024"})
        self.assertTrue(climate.reference_verified.eq(1).all())
        pfep = self.relations[self.relations.target_type.eq("PFEP") & self.relations.target_id.ne("")]
        self.assertTrue(pfep.target_id.str[0].eq(pfep.project_letter).all())

    def test_system_component_disambiguates_variable(self):
        row = self.relations_for("A 1.78")
        var = row[row.target_type.eq("SKB_VARIABLE")]
        self.assertEqual(set(var.target_id), {"VarF05"})
        self.assertTrue(var.identifier_resolution.eq("exact_name_and_component").all())

    def test_unknown_selected_variable_remains_unresolved(self):
        row = self.relations_for("J 5.21")
        var = row[row.target_type.eq("SKB_VARIABLE")]
        self.assertEqual(set(var.target_name), {"Initial state general"})
        self.assertTrue(var.target_id.eq("").all())
        self.assertTrue(var.target_exists_in_stage.eq("no").all())
        self.assertTrue(var.reference_verified.eq(0).all())

    def test_sr_can_targets_are_real_but_not_sr_site_targets(self):
        row = self.relations[self.relations.source_field.eq("SRCANBIOSPHEREFEP LIST")]
        self.assertEqual(row.source_pfep_id.nunique(), 6)
        self.assertEqual(len(row), 11)
        self.assertTrue(row.stage.eq("SR-Can").all())
        self.assertTrue(row.target_exists_in_stage.eq("yes").all())
        self.assertTrue(row.target_present_in_srsite_catalogue.eq("no").all())
        self.assertTrue(row.current_skb_adoption_documented.eq(0).all())

    def test_repeated_safe_family_is_not_a_unique_matrix_cell(self):
        row = self.relations_for("J 7.02")
        self.assertEqual(set(row.stage), {"SAFE"})
        self.assertTrue(row.candidate_count.gt(1).all())
        self.assertTrue(row.target_id.eq("").all())
        self.assertEqual(self.records.loc["J 7.02", "documentary_unresolved"], 1)
        self.assertEqual(self.records.loc["J 7.02", "documentary_class"], "Earlier-stage SKB association")

    def test_retained_handling_links_preserve_status_conflict(self):
        row = self.relations_for("W 1.072")
        links = row[row.origin_layer.eq("skb_handling_table")]
        self.assertEqual(len(links), 9)
        self.assertTrue(links.status_conflict.eq(1).all())
        self.assertTrue(links.current_skb_adoption_documented.eq(0).all())

    def test_excluded_target_is_resolvable_but_not_relevant(self):
        source = self.records.loc["J 5.18"]
        self.assertEqual(source.documentary_unresolved, 0)
        self.assertEqual(source.no_resolved_relevant_destination, 1)
        self.assertEqual(source.n_benchmark_destinations, 0)
        self.assertEqual(source.resolved_destination_ids, "J 4.2.05")

    def test_every_evidence_span_roundtrips_to_its_original_field(self):
        for row in self.relations.itertuples():
            container = self.snapshot["records"][row.source_pfep_id][row.raw_source_file]
            if isinstance(container, list):
                container = next(r for r in container if r["source_record_id"] == row.source_record_id)
            value = container[row.source_field]
            self.assertEqual(value[row.span_start:row.span_end], row.evidence_span)

    def test_numeric_substrings_cannot_be_resolved_as_whole_identifiers(self):
        rules = copy.deepcopy(self.rules)
        rules["records"]["J 2.3.02"]["references"][0]["targets"] = ["1.1"]
        with self.assertRaisesRegex(ValueError, "whole numeric token"):
            build(self.snapshot, rules)

    def test_physical_quantity_noise_does_not_create_reference_edges(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["records"]["W 2.072"]["PROFEP.KSE"]["FEP DESCRIPTION"] += "\rMeasurements: 1.1 years, 1.4 MPa, 1.5 moles, 3.6 kilograms."
        _, rel = build(snapshot, self.rules)
        before = self.relations_for("W 2.072")
        after = rel[rel.source_pfep_id.eq("W 2.072")]
        self.assertEqual(set(before.relation_id), set(after.relation_id))


if __name__ == "__main__":
    unittest.main()
