"""Regression tests for the new summaries; not independent scientific validation."""
import json
import unittest
from pathlib import Path
from compute_record_analysis import read_csv, aggregate_endpoints, review_queue, branch_summary, source_aspects
P = Path(__file__).resolve().parents[1] / 'data'

class NTRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics, cls.source = aggregate_endpoints(read_csv(P / 'retrieval_rank_comparison_pairs.csv'))
        cls.cohort = [r for r in read_csv(P / 'coverage_evidence_200.csv') if r['project_letter'] != 'N']

    def selected(self, gate):
        return next(r for r in self.metrics if r['query_variant'] == 'unmasked'
                    and r['model'] == 'archived_weighted_score' and r['k'] == 10
                    and r['eligibility_rule'] == gate)

    def test_configuration_denominators(self):
        self.assertEqual(len(self.metrics), 96)
        self.assertTrue(all(r['sources_n'] == 18 and r['attested_endpoints_n'] == 42 for r in self.metrics))

    def test_gated_metrics(self):
        r = self.selected('shared_IFEP_required')
        self.assertEqual((r['hit_sources_n'], r['recovered_endpoints_n'], r['complete_sets_n']), (15,18,12))
        self.assertEqual(r['multi_endpoint_complete_sets_n'], 2)

    def test_ungated_metrics(self):
        r = self.selected('no_IFEP_eligibility_filter')
        self.assertEqual((r['hit_sources_n'], r['recovered_endpoints_n'], r['complete_sets_n']), (14,23,10))
        self.assertEqual(r['multi_endpoint_complete_sets_n'], 2)

    def test_eligibility_ceilings(self):
        r = self.selected('shared_IFEP_required')
        self.assertEqual((r['eligible_endpoints_n'], r['all_endpoints_eligible_sources_n']), (19,12))
        for r in self.metrics:
            self.assertLessEqual(r['recovered_endpoints_n'], r['eligible_endpoints_n'])
            self.assertLessEqual(r['complete_sets_n'], r['all_endpoints_eligible_sources_n'])

    def test_review_partition_and_observability(self):
        q, s = review_queue(self.cohort)
        self.assertEqual(sorted(s['identity_tasks'].values()), [17,19,19])
        self.assertEqual((len(q), s['relation_specific_SR_Site_adoption_observed'],
                          s['earlier_stage_adoption_observed'], s['additional_scope_rationale_text_observed']), (55,0,3,5))
        self.assertTrue(all(r['technical_adequacy'] == 'not_independently_assessed' for r in q))

    def test_branch_inventory_matches_full_graph(self):
        branches = branch_summary(json.loads((P/'technical_case_handling_rows.json').read_text()),
                                  read_csv(P/'pfep_srsite_network_edges.csv'))
        self.assertEqual([r['handling_rows_n'] for r in branches], [1,5,19,1])
        self.assertEqual(sum(r['handled_text_rows_n'] for r in branches), 22)
        self.assertEqual(sum(r['comment_rows_n'] for r in branches), 20)

    def test_source_aspect_spans(self):
        aspects = source_aspects(self.cohort)
        text = next(r['imported_description_raw'] for r in self.cohort if r['pfep_id']=='H 1.6.3')
        self.assertEqual(len(aspects), 10)
        for r in aspects:
            self.assertEqual(text[r['span_start']:r['span_end']], r['source_aspect_literal'])
            self.assertEqual(r['aspect_specific_target'], '')

if __name__ == '__main__':
    unittest.main()
