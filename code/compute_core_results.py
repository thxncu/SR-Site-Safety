"""Compute the documentary, lookup, population and association summaries."""
from pathlib import Path
from collections import defaultdict
import json
import re
import sys
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
sys.path.insert(0, str(ROOT/'code/semantic'))
from traceability_semantics import norm, ifeps
CLASSES = ['SR-Site-stage SKB association', 'Earlier-stage SKB association',
           'Original-inventory reference', 'SKB rationale without identifiable destination',
           'No identifiable documentary destination']

def read(name):
    return pd.read_csv(DATA/name, keep_default_na=False)

def v(frame):
    a = pd.crosstab(frame.project_letter, frame.relevance).to_numpy()
    n = a.sum(); r, k = a.shape
    phi = max(0, chi2_contingency(a, correction=False)[0]/n-(r-1)*(k-1)/(n-1))
    return float(np.sqrt(phi/min(r-(r-1)**2/(n-1)-1, k-(k-1)**2/(n-1)-1)))

def numeric(identifier):
    m = re.fullmatch(r'([A-Z])\s+(\d+(?:\.\d+)*)', identifier)
    return (m[1], tuple(map(int, m[2].split('.')))) if m else None

def lookups(pop, cov):
    rows=[]; idx=pop.set_index('pfep_id')
    targets=pop[pop.relevance.str.lower().eq('relevant')].to_dict('records')
    for s in cov.itertuples(index=False):
        src=idx.loc[s.pfep_id]; sk=numeric(s.pfep_id)
        sf=ifeps(src.get('international_fep_numbers_all',src.get('international_fep_number','')))
        for t in targets:
            if t['pfep_id']==s.pfep_id:continue
            methods=[];tk=numeric(t['pfep_id'])
            if norm(src.pfep_name) and norm(src.pfep_name)==norm(t['pfep_name']):methods.append('normalized_exact_title')
            if sk and tk and sk[0]==tk[0] and len(tk[1])>len(sk[1]) and tk[1][:len(sk[1])]==sk[1]:methods.append('same_inventory_identifier_descendant')
            shared=sf & ifeps(t.get('international_fep_numbers_all',t.get('international_fep_number','')))
            for method in methods:
                rows.append(dict(source_pfep_id=s.pfep_id,source_pfep_name=src.pfep_name,project_letter=src.project_letter,
                    target_pfep_id=t['pfep_id'],target_pfep_name=t['pfep_name'],method=method,shared_ifep_count=len(shared),
                    shared_ifep_ids='; '.join(sorted(shared)),documentary_unresolved=int(s.documentary_unresolved),
                    relation_origin='analytical_lookup',official_coverage_relation=0))
    edges=pd.DataFrame(rows);edges.to_csv(DATA/'lookup_candidate_relations.csv',index=False)
    summary=[]
    for scope,ids in [('All coverage decisions',set(cov.pfep_id)),('Documentary unresolved',set(cov.loc[cov.documentary_unresolved.eq(1),'pfep_id']))]:
        for method in ['normalized_exact_title','same_inventory_identifier_descendant']:
            for gate in ['No taxonomy restriction','Shared IFEP required']:
                f=edges[edges.source_pfep_id.isin(ids)&edges.method.eq(method)]
                if gate=='Shared IFEP required':f=f[f.shared_ifep_count.gt(0)]
                counts=f.groupby('source_pfep_id').target_pfep_id.nunique()
                summary.append(dict(scope=scope,source_population_n=len(ids),method=method,eligibility_rule=gate,
                    sources_with_candidates_n=len(counts),candidate_relations_n=len(f),sources_with_multiple_candidates_n=int(counts.gt(1).sum()),
                    candidate_relations_without_shared_ifep_n=int(f.shared_ifep_count.eq(0).sum()),
                    project_N_sources_n=int(f.loc[f.project_letter.eq('N'),'source_pfep_id'].nunique())))
    pd.DataFrame(summary).to_csv(DATA/'lookup_candidate_summary.csv',index=False)
    return summary

def graph(pop,edges,cat):
    relevant=edges[edges.pfep_id.isin(set(pop.loc[pop.relevance.str.lower().eq('relevant'),'pfep_id']))]
    tids=set(edges.sr_id);cids=set(cat.sr_id);deg=edges.groupby('sr_id').pfep_id.nunique().sort_values(ascending=False)
    names=cat.set_index('sr_id').sr_name.to_dict()
    pd.DataFrame([dict(sr_id=t,sr_name=names.get(t,''),degree_pfep=int(n)) for t,n in deg.items()]).to_csv(DATA/'srsite_fep_network_metrics.csv',index=False)
    annotations=[]
    for scope,f in [('All archived associations',edges),('Finally relevant PFEP associations',relevant)]:
        h=f.handled_flag.eq(1);u=f.unhandled_flag.eq(1)
        for label,mask in [('Handled-aspects text only',h&~u),('Unhandled-because text only',~h&u),('Both annotation fields',h&u),('Neither annotation field',~h&~u)]:
            annotations.append(dict(scope=scope,annotation_pattern=label,association_n=int(mask.sum())))
    pd.DataFrame(annotations).to_csv(DATA/'handling_annotation_patterns.csv',index=False)
    adjacency=defaultdict(set)
    for a,b in edges[['pfep_id','sr_id']].itertuples(index=False,name=None):
        a='P:'+a;b='T:'+b;adjacency[a].add(b);adjacency[b].add(a)
    visited=set();sizes=[]
    for node in adjacency:
        if node in visited:continue
        reached={node};todo=[node]
        while todo:
            fresh=adjacency[todo.pop()]-reached;reached.update(fresh);todo.extend(fresh)
        visited.update(reached);sizes.append(len(reached))
    return dict(archived_associations_n=len(edges),relevant_associations_n=len(relevant),excluded_source_associations_n=len(edges)-len(relevant),
        archived_pfep_nodes_n=int(edges.pfep_id.nunique()),relevant_pfep_nodes_n=int(relevant.pfep_id.nunique()),
        target_identifiers_n=len(tids),matched_catalogue_identifiers_n=len(tids&cids),unmatched_target_identifiers=sorted(tids-cids),
        catalogue_records_n=len(cat),unlinked_catalogue_records_n=len(cids-tids),connected_components_n=len(sizes),
        largest_component_nodes_n=max(sizes),top_ten_target_share=float(deg.head(10).sum()/len(edges)),annotation_patterns=annotations)

def main():
    pop=read('pfep_relevance_population_1671.csv');nr=read('not_relevant_370_normalized.csv');cb=read('phrase_codebook_23.csv')
    cov=read('coverage_evidence_200.csv');rel=read('provenance_relations.csv')
    labels={'Taxonomic absorption':'Coverage elsewhere','Contextual localization':'System applicability','Ontological nullification':'Non-FEP designation'}
    ops=nr.relevance_motivation_clean.map(cb.set_index('relevance_motivation_clean').screening_operation).replace(labels)
    if ops.isna().any() or set(cov.pfep_id)!=set(nr.loc[ops.eq('Coverage elsewhere'),'pfep_id']):raise ValueError('Coverage population and codebook differ')
    for f in [pop,nr,cov]:
        if f.pfep_id.duplicated().any():raise ValueError('Duplicate source identifiers')
    if set(cov.documentary_class)-set(CLASSES):raise ValueError('Unspecified documentary class')
    distributions=[];properties=[]
    flag_names=[c for c in cov if c.endswith('_present') or c.endswith('_documented') or c in ['documentary_unresolved','no_resolved_relevant_destination','formal_reason_coverage_assertion']]
    for group,f in [('All',cov),('Project N',cov[cov.project_letter.eq('N')]),('Other inventories',cov[cov.project_letter.ne('N')])]:
        for cls in CLASSES:
            t=f[f.documentary_class.eq(cls)];distributions.append(dict(inventory_group=group,group_n=len(f),documentary_class=cls,sources_n=len(t),percent=len(t)/len(f)*100,sources_with_resolved_destinations_n=int(t.documentary_unresolved.eq(0).sum())))
        for c in flag_names:properties.append(dict(inventory_group=group,source_n=len(f),property=c,present_n=int(f[c].astype(int).sum())))
    pd.DataFrame(distributions).to_csv(DATA/'documentary_class_distribution.csv',index=False)
    pd.DataFrame(properties).to_csv(DATA/'documentary_properties.csv',index=False)
    lookup=lookups(pop,cov);loo=[]
    for p in sorted(pop.project_letter.unique()):
        mask=nr.project_letter.ne(p);f=pop[pop.project_letter.ne(p)]
        loo.append(dict(left_out_project=p,n_population=len(f),cramers_v_project_relevance=v(f),not_relevant_n=int(mask.sum()),
                        coverage_elsewhere_n=int((mask&ops.eq('Coverage elsewhere')).sum()),system_applicability_n=int((mask&ops.eq('System applicability')).sum()),non_fep_designation_n=int((mask&ops.eq('Non-FEP designation')).sum())))
    pd.DataFrame(loo).to_csv(DATA/'leave_one_project_out_sensitivity.csv',index=False)
    edges=read('pfep_srsite_network_edges.csv')
    if edges.duplicated(['pfep_id','sr_id']).any():raise ValueError('Handling rows must be unique associations')
    network=graph(pop,edges,read('srsite_catalogue_407.csv'));reviews=read('external_review_findings_42.csv')
    reviews.groupby(['source','primary_dimension']).size().rename('passage_n').reset_index().to_csv(DATA/'external_review_composition.csv',index=False)
    out=dict(screened_population_n=len(pop),relevant_n=int(pop.relevance.str.lower().eq('relevant').sum()),not_relevant_n=len(nr),coverage_n=len(cov),
        screening_operations=ops.value_counts().to_dict(),exact_reason_phrases_n=int(nr.relevance_motivation_clean.nunique()),documentary_classes=cov.documentary_class.value_counts().to_dict(),
        documentary_unresolved_n=int(cov.documentary_unresolved.sum()),sources_with_resolved_documentary_destination_n=int(cov.documentary_unresolved.eq(0).sum()),provenance_relations_n=len(rel),
        resolved_destination_multiplicity={str(k):int(val) for k,val in cov.loc[cov.n_unique_resolved_destinations.gt(0),'n_unique_resolved_destinations'].value_counts().sort_index().items()},
        documentary_properties={r['property']:r['present_n'] for r in properties if r['inventory_group']=='All'},lookup_candidates=lookup,
        cramers_v_all=v(pop),cramers_v_without_N=v(pop[pop.project_letter.ne('N')]),network=network,external_review_passages_n=len(reviews),
        external_review_source_counts=reviews.source.value_counts().to_dict(),external_review_category_counts=reviews.primary_dimension.value_counts().to_dict(),
        retrieval=json.loads((DATA/'retrieval_summary.json').read_text()))
    (DATA/'analysis_summary.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'documentary_classes':out['documentary_classes'],'documentary_unresolved_n':out['documentary_unresolved_n'],'summary':'data/analysis_summary.json'},indent=2))

if __name__=='__main__':main()
