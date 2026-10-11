"""Regression checks for missing text, taxonomy gates and benchmark denominators."""
import unittest
import numpy as np
import pandas as pd

from traceability_semantics import (
    build_components, rank_candidates, conditional_outcome, benchmark_rank, score,
)
from recompute_semantic_scores import (
    search_results, benchmark_results, threshold_sensitivity,
    PRIMARY_MODEL, PRIMARY_GATE,
)


def fixture():
    source = pd.DataFrame([
        dict(pfep_id="N 1.1", pfep_name="Groundwater flow", project_letter="N",
             pfep_description="", pfep_comments="", comments_needs_discussion="",
             assessment_basis_comment="", international_fep_numbers_all="1.1"),
        dict(pfep_id="A 1.2", pfep_name="Buffer alteration", project_letter="A",
             pfep_description="Bentonite chemistry and alteration in water", pfep_comments="",
             comments_needs_discussion="", assessment_basis_comment="",
             international_fep_numbers_all=""),
    ])
    relevant = pd.DataFrame([
        dict(pfep_id="M 1.01", pfep_name="Groundwater flow", project_letter="M",
             pfep_description="Groundwater flow", pfep_comments="",
             international_fep_numbers_all="1.1"),
        dict(pfep_id="M 1.02", pfep_name="Buffer chemistry", project_letter="M",
             pfep_description="Bentonite chemistry and alteration in water", pfep_comments="",
             international_fep_numbers_all="2.2"),
    ])
    decisions = pd.DataFrame([
        dict(pfep_id="N 1.1", documentary_class="No identifiable destination", documentary_unresolved=True),
        dict(pfep_id="A 1.2", documentary_class="Original inventory reference", documentary_unresolved=False),
    ])
    return source, relevant, decisions


class RetrievalRegressionTests(unittest.TestCase):
    def test_eligibility_precedes_ranking_and_no_pool_differs_from_low_score(self):
        scores = np.array([0.95, 0.35, 0.30])
        order = rank_candidates(scores, np.array([0, 1, 1]), ["A", "B", "C"])
        self.assertEqual(order, [1, 2])
        self.assertEqual(conditional_outcome(order, scores, 0.34), "candidate_at_or_above_threshold")
        self.assertEqual(conditional_outcome(order, scores, 0.40), "best_eligible_below_threshold")
        self.assertEqual(conditional_outcome([], scores, 0.34), "no_eligible_candidate")

    def test_missing_body_is_exactly_title_ablation_and_fallback_does_not_refit(self):
        source, relevant, _ = fixture()
        comp = build_components(source, relevant)
        models = comp.model_scores()
        self.assertEqual(comp.source_text_empty.tolist(), [True, False])
        self.assertTrue(np.all(comp.word[0] == 0))
        self.assertTrue(np.all(comp.character[0] == 0))
        self.assertTrue(np.array_equal(models[PRIMARY_MODEL][0], models["title_only_ablation"][0]))
        self.assertTrue(np.array_equal(models[PRIMARY_MODEL][1], models["missing_text_title_fallback"][1]))
        self.assertGreater(models["missing_text_title_fallback"][0, 0], models[PRIMARY_MODEL][0, 0])

    def test_documentary_class_is_unchanged_by_candidate_retention(self):
        source, relevant, decisions = fixture()
        before = decisions.copy(deep=True)
        comp = build_components(source, relevant)
        outcomes, _, _ = search_results(comp, decisions, comp.model_scores())
        pd.testing.assert_frame_equal(decisions, before)
        selected = outcomes[outcomes.model.eq(PRIMARY_MODEL) & outcomes.eligibility_rule.eq(PRIMARY_GATE)]
        n_row = selected[selected.source_pfep_id.eq("N 1.1")].iloc[0]
        self.assertEqual(n_row.search_outcome, "candidate_at_or_above_threshold")
        self.assertEqual(n_row.documentary_class, "No identifiable destination")
        self.assertEqual(n_row.documentary_unresolved, 1)
        summaries = threshold_sensitivity(outcomes)
        totals = (summaries.candidate_at_or_above_threshold_n
                  + summaries.best_eligible_below_threshold_n + summaries.no_eligible_candidate_n)
        self.assertTrue(np.array_equal(totals, summaries.documentary_unresolved_n))

    def test_taxonomy_ineligible_gold_remains_a_benchmark_miss(self):
        source, relevant, decisions = fixture()
        comp = build_components(source, relevant)
        models = comp.model_scores()
        _, _, orders = search_results(comp, decisions, models)
        relations = pd.DataFrame([
            dict(source_pfep_id=s, target_id="M 1.02", target_type="PFEP",
                 origin_layer="original_inventory", source_field="pfep_description",
                 relation_semantics="treatment_endpoint", evidence_span="Treatment is in FEP M 1.02.",
                 direction_valid=True, reference_verified=True, benchmark_eligible=True)
            for s in source.pfep_id
        ])
        cases, summaries, _ = benchmark_results(comp, relations, models, orders)
        result = summaries[summaries.benchmark_scope.eq("strict_source_endpoints")
                           & summaries.model.eq(PRIMARY_MODEL)
                           & summaries.eligibility_rule.eq(PRIMARY_GATE)].iloc[0]
        self.assertEqual(result.n_source_cases, 2)
        self.assertEqual(result.no_endpoint_eligible_n, 2)
        self.assertEqual(result.no_eligible_candidate_n, 1)
        self.assertEqual(result.hit_at_10_fraction, 0.0)
        unrestricted = summaries[summaries.benchmark_scope.eq("strict_source_endpoints")
                                 & summaries.model.eq(PRIMARY_MODEL)
                                 & summaries.eligibility_rule.eq("no_IFEP_eligibility_filter")].iloc[0]
        self.assertEqual(unrestricted.hit_at_10_n, 2)

    def test_constant_removal_requires_a_transformed_cutoff(self):
        W = np.array([[0.1, 0.5]])
        C = np.array([[0.2, 0.4]])
        T = np.array([[0.3, 0.8]])
        F = np.ones((1, 2))
        baseline = score(W, C, T, F)
        removed = score(W, C, T, F, (0.35 / 0.85, 0.25 / 0.85, 0.25 / 0.85, 0.0))
        self.assertTrue(np.allclose(removed, (baseline - 0.15) / 0.85))
        self.assertTrue(np.array_equal(baseline >= 0.34, removed >= (0.34 - 0.15) / 0.85))
        self.assertEqual(rank_candidates(baseline[0], F[0], ["A", "B"]),
                         rank_candidates(removed[0], F[0], ["A", "B"]))


if __name__ == "__main__":
    unittest.main()
