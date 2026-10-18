#!/usr/bin/env python3
"""Compare three nested relation-selection rules for the fixed 55-record cohort."""
from pathlib import Path
import sys
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'code/extraction'))
from build_covered_elsewhere_audit import ASSOCIATION_SEMANTICS
CONTEXTUAL = {'see_also', 'related_discussion', 'specific_factor_reference'}
KEYS = ['source_pfep_id', 'target_type', 'target_id', 'target_stage']

def summarize(relations, cohort):
    """Use existing labels, directions and lookups; retain every cohort member."""
    ids = list(cohort.pfep_id)
    r = relations[relations.source_pfep_id.isin(ids)]
    principal = r[r.relation_semantics.isin(ASSOCIATION_SEMANTICS)
                  & r.direction_valid.eq(1)
                  & r.target_exists_in_stage.eq('yes') & r.ambiguity.eq('none')]
    relevant = principal[principal.target_type.ne('PFEP')
                         | principal.target_relevance.str.lower().eq('relevant')]
    treatment = relevant[~relevant.relation_semantics.isin(CONTEXTUAL)]
    rules = [('R1', 'Principal identity rule', principal),
             ('R2', 'Relevant PFEP or stage-qualified SKB target', relevant),
             ('R3', 'R2 with contextual-only relation types excluded', treatment)]
    output, summary = [], []
    baseline = set(principal.source_pfep_id)
    for code, label, frame in rules:
        unique = frame.drop_duplicates(KEYS)
        counts = unique.groupby('source_pfep_id').size().reindex(ids, fill_value=0)
        current = set(frame.source_pfep_id)
        for pid in ids:
            targets = unique[unique.source_pfep_id.eq(pid)]
            output.append({'rule':code, 'pfep_id':pid,
                           'resolved_targets_n':int(counts[pid]),
                           'task':('destination_identification' if counts[pid]==0 else
                                   'single_destination_scope' if counts[pid]==1 else
                                   'distributed_scope'),
                           'target_keys':'; '.join(sorted('|'.join(str(row[k]) for k in KEYS[1:])
                                                       for _,row in targets.iterrows()))})
        summary.append({'rule':code,'selection':label,'sources_n':len(ids),
                        'resolved_sources_n':int((counts>0).sum()),
                        'destination_identification_n':int((counts==0).sum()),
                        'single_destination_scope_n':int((counts==1).sum()),
                        'distributed_scope_n':int((counts>1).sum()),
                        'sources_resolved_only_by_R1':'; '.join(sorted(baseline-current))})
    return pd.DataFrame(output),pd.DataFrame(summary)

if __name__=='__main__':
    data=ROOT/'data'
    r=pd.read_csv(data/'provenance_relations.csv', keep_default_na=False)
    c=pd.read_csv(data/'non_project_n_census_55.csv', keep_default_na=False)
    sources, summary=summarize(r,c)
    sources.to_csv(data/'relation_rule_sensitivity_sources.csv',index=False)
    summary.to_csv(data/'relation_rule_sensitivity_summary.csv',index=False)
    print(summary.to_string(index=False))
