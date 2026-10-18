#!/usr/bin/env python3
"""Regression and synthetic checks, not independent scientific validation."""
import copy, json, unittest
from pathlib import Path
import numpy as np
import pandas as pd
from compute_retrieval_robustness import BM25Index, estimate, record_fixtures, ROOT

class VerificationExtensionTests(unittest.TestCase):
    def test_bm25_exact_small_example(self):
        model=BM25Index(['buffer buffer corrosion','buffer chemistry','fracture'])
        expected=np.log1p((3-2+.5)/(2+.5)) * 2*2.2/(2+1.2*(.25+.75*3/2))
        self.assertAlmostEqual(model.scores(['buffer'])[0,0],expected)
    def test_bm25_binary_query_terms(self):
        m=BM25Index(['buffer corrosion','buffer buffer chemistry'])
        np.testing.assert_allclose(m.scores(['buffer']),m.scores(['buffer buffer']))
    def test_bm25_unknown_empty_query(self):
        m=BM25Index(['buffer corrosion','fracture'])
        np.testing.assert_array_equal(m.scores(['','xylophonium']),np.zeros((2,2)))
    def test_parameter_bounds(self):
        with self.assertRaises(ValueError): BM25Index(['buffer'],b=2)
    def test_ratio_resampling_keeps_source_denominators(self):
        idx=np.array([[0,0,1],[1,1,0]])
        got=estimate((np.array([1,2]),np.array([1,4])),idx)
        np.testing.assert_allclose(got,[4/6,5/9])
    def test_28_configurations_have_same_benchmark(self):
        df=pd.read_csv(ROOT/'data/robustness_all_28_configs_by_source.csv')
        g=df[df.k.eq(10)].groupby(['query_variant','model','eligibility_rule'])
        self.assertEqual(len(g),28)
        for _,f in g:
            self.assertEqual(f.source_pfep_id.nunique(),18)
            self.assertEqual(f.attested_endpoints_n.sum(),42)
    def test_paired_reference_is_exact_zero(self):
        d=pd.read_csv(ROOT/'data/robustness_retrieval_paired_differences.csv')
        f=d[d.model.eq('archived_weighted_score') & d.query_variant.eq('unmasked') & d.eligibility_rule.eq('shared_IFEP_required')]
        np.testing.assert_array_equal(f[['estimate_difference','lower_025','upper_975']].values,np.zeros((4,3)))
    def test_all_synthetic_faults_and_control(self):
        rows=record_fixtures(ROOT)
        self.assertEqual(len(rows),14)
        self.assertTrue(all(r['passed'] for r in rows))
        self.assertEqual(rows[0]['fixture_kind'],'observed_example')
    def test_source_and_inventory_omission_units(self):
        a=pd.read_csv(ROOT/'data/robustness_leave_one_source.csv')
        self.assertTrue(a.sources_n.eq(17).all())
        b=pd.read_csv(ROOT/'data/robustness_leave_one_inventory.csv')
        self.assertTrue(b[b.omitted_inventory.eq('J')].sources_n.eq(7).all())

if __name__=='__main__': unittest.main()
