"""Tests for nested relation-selection summaries."""
import unittest
from pathlib import Path
import pandas as pd
from compute_relation_sensitivity import summarize
ROOT=Path(__file__).resolve().parents[1]
class RelationSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=pd.read_csv(ROOT/'data/non_project_n_census_55.csv',keep_default_na=False)
        cls.r=pd.read_csv(ROOT/'data/provenance_relations.csv',keep_default_na=False)
        cls.sources,cls.summary=summarize(cls.r,cls.c)
    def test_fixed_population(self):
        for _,g in self.sources.groupby('rule'):
            self.assertEqual(set(g.pfep_id),set(self.c.pfep_id))
            self.assertEqual(len(g),55)
    def test_principal_matches_census(self):
        a=self.sources[self.sources.rule.eq('R1')].set_index('pfep_id').resolved_targets_n
        b=self.c.set_index('pfep_id').n_unique_resolved_destinations
        self.assertTrue(a.sort_index().equals(b.sort_index()))
    def test_nesting(self):
        v=self.sources.pivot(index='pfep_id',columns='rule',values='resolved_targets_n')
        self.assertTrue((v.R1>=v.R2).all() and (v.R2>=v.R3).all())
    def test_changed_sources(self):
        s=self.summary.set_index('rule')
        self.assertEqual(list(s.resolved_sources_n),[36,35,33])
        self.assertEqual(s.loc['R2','sources_resolved_only_by_R1'],'J 5.18')
        self.assertEqual(s.loc['R3','sources_resolved_only_by_R1'],'A 1.39; J 5.18; W 2.072')
if __name__=='__main__':unittest.main()
