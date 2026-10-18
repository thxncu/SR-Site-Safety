#!/usr/bin/env python3
"""Compute fixed BM25 retrieval, source-resampling sensitivity and checker fixtures.

All benchmark configurations use the same recorded sources and endpoint sets.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, os, platform, sys, time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'code'), str(ROOT/'code/semantic'), str(ROOT/'code/record_checks')]
from traceability_semantics import load_population, _text, CANDIDATE_FIELDS, ifeps, rank_candidates
from compute_record_analysis import aggregate_endpoints
from check_screening_record import check_record

VERSION = '3.1.0'
SEED = 20261017
DRAWS = 10000
COLUMNS = ['query_variant', 'model', 'eligibility_rule']


def write_csv(path: Path, rows) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


class BM25Index:
    """Exact floating-point BM25 with candidate-only document statistics.

    Uses unique query terms (binary query weights), English stop words, the
    scikit-learn default two-character token rule, and no query expansion.
    This is NOT a byte-for-byte reproduction of Lucene indexing/length norms.
    """
    def __init__(self, documents: list[str], k1: float = 1.2, b: float = .75):
        if not documents or not np.isfinite(k1) or k1 < 0 or not 0 <= b <= 1:
            raise ValueError('Invalid BM25 parameters or empty collection.')
        self.vectorizer = CountVectorizer(stop_words='english', ngram_range=(1, 1))
        matrix = self.vectorizer.fit_transform(documents).astype(float).tocsc()
        self.k1, self.b = k1, b
        n = matrix.shape[0]
        lengths = np.asarray(matrix.sum(axis=1)).ravel()
        self.average_length = float(lengths.mean())
        if self.average_length <= 0:
            raise ValueError('No candidate tokens.')
        df = np.diff(matrix.indptr)
        idf = np.log1p((n-df+.5)/(df+.5))
        norm = k1*(1-b+b*lengths/self.average_length)
        for col in range(matrix.shape[1]):
            sl = slice(matrix.indptr[col], matrix.indptr[col+1])
            tf = matrix.data[sl]
            matrix.data[sl] = idf[col]*(tf*(k1+1))/(tf+norm[matrix.indices[sl]])
        self.weighted = matrix.tocsr()

    def scores(self, queries: list[str]) -> np.ndarray:
        query = self.vectorizer.transform(queries)
        query.data[:] = 1
        return (query @ self.weighted.T).toarray()


def bm25_pairs(data: Path):
    _, source, relevant = load_population(data)
    query = pd.read_csv(data/'retrieval_benchmark_query_texts.csv', keep_default_na=False)
    existing = pd.read_csv(data/'retrieval_rank_comparison_pairs.csv', keep_default_na=False)
    gold = existing[['source_pfep_id','verified_endpoint_id']].drop_duplicates()
    ids = relevant.pfep_id.tolist()
    source_index = source.set_index('pfep_id')
    candidate_sets = relevant.international_fep_numbers_all.map(ifeps).tolist()
    docs = _text(relevant, CANDIDATE_FIELDS).tolist()
    start=time.perf_counter(); index = BM25Index(docs); index_s = time.perf_counter()-start
    rows, top, timings = [], [], []
    for variant, field in [('unmasked','unmasked_query'),('audited_numeric_identifiers_masked','identifier_masked_query')]:
        scores=index.scores(query[field].tolist())
        for qi, src in enumerate(query.source_pfep_id):
            srcset=ifeps(source_index.loc[src, 'international_fep_numbers_all'])
            shared=np.array([len(srcset & s) for s in candidate_sets])
            targets=gold.loc[gold.source_pfep_id.eq(src), 'verified_endpoint_id'].tolist()
            for gate in (True, False):
                eligibility='shared_IFEP_required' if gate else 'no_IFEP_eligibility_filter'
                order=rank_candidates(scores[qi],shared,ids,excluded=(src,),require_shared=gate)
                positions={ids[j]:rank for rank,j in enumerate(order,1)}
                for target in targets:
                    j=ids.index(target)
                    rows.append(dict(query_variant=variant,model='bm25_fixed',eligibility_rule=eligibility,
                                     source_pfep_id=src,verified_endpoint_id=target,
                                     endpoint_shares_ifep=int(shared[j]>0),endpoint_eligible=int(target in positions),
                                     endpoint_rank=positions.get(target,''),endpoint_score=float(scores[qi,j])))
                for rank,j in enumerate(order[:20],1):
                    top.append(dict(query_variant=variant,model='bm25_fixed',eligibility_rule=eligibility,
                                    source_pfep_id=src,rank=rank,candidate_id=ids[j],score=float(scores[qi,j]),
                                    attested_endpoint=int(ids[j] in targets)))
    # Informative timing only. No baseline speedup is inferred from this boundary.
    for rep in range(5):
        start=time.perf_counter(); index.scores(query.unmasked_query.tolist())
        timings.append(dict(operation='BM25 scoring 18 unmasked queries; index prebuilt; no sorting or I/O',
                            repetition=rep+1,elapsed_seconds=time.perf_counter()-start))
    write_csv(data/'robustness_bm25_pairs.csv', rows)
    write_csv(data/'robustness_bm25_top20.csv', top)
    metrics,sources=aggregate_endpoints([{k:str(v) for k,v in r.items()} for r in rows])
    write_csv(data/'robustness_bm25_metrics.csv',metrics)
    write_csv(data/'robustness_bm25_by_source.csv',sources)
    return metrics, sources, {'candidate_documents_n':len(docs),'vocabulary_n':len(index.vectorizer.vocabulary_),
                              'average_candidate_tokens':index.average_length,'index_build_seconds':index_s,
                              'scoring_timings':timings}


def measures(frame: pd.DataFrame):
    den=frame.attested_endpoints_n.to_numpy(float)
    rec=frame.recovered_endpoints_n.to_numpy(float)
    return {'hit':frame.hit.to_numpy(float),'complete_set':frame.complete_set.to_numpy(float),
            'recall_micro':(rec,den), 'recall_macro':rec/den}


def estimate(x, indices=None):
    if isinstance(x,tuple):
        a,b=x
        return float(a.sum()/b.sum()) if indices is None else a[indices].sum(1)/b[indices].sum(1)
    return float(x.mean()) if indices is None else x[indices].mean(1)


def summarize_sensitivity(data:Path, additional_sources:list):
    original=pd.read_csv(data/'record_endpoint_metrics_by_source.csv',keep_default_na=False)
    full=pd.concat([original,pd.DataFrame(additional_sources)],ignore_index=True)
    for c in ['k','attested_endpoints_n','recovered_endpoints_n','hit','complete_set']:
        full[c]=pd.to_numeric(full[c])
    selected=full[full.k.eq(10)].copy()
    selected['inventory']=selected.source_pfep_id.str.split().str[0]
    ids=sorted(selected.source_pfep_id.unique()); assert len(ids)==18
    rng=np.random.Generator(np.random.PCG64(SEED))
    indices=rng.integers(0,len(ids),size=(DRAWS,len(ids)))
    groups={config:f.set_index('source_pfep_id').loc[ids].reset_index() for config,f in selected.groupby(COLUMNS,sort=True)}
    ref=('unmasked','archived_weighted_score','shared_IFEP_required')
    reference=measures(groups[ref])
    ci, delta, leave_source, leave_inventory=[],[],[],[]
    for config,frame in groups.items():
        base=dict(zip(COLUMNS,config)); vals=measures(frame)
        for metric,x in vals.items():
            distribution=estimate(x,indices); point=estimate(x)
            lo,hi=np.quantile(distribution,[.025,.975],method='linear')
            ci.append(base|dict(k=10,metric=metric,estimate=point,lower_025=float(lo),upper_975=float(hi),
                                bootstrap_draws=DRAWS,sources_n=18,seed=SEED,
                                interpretation='conditional_source_resampling_sensitivity_not_population_CI'))
            dif=distribution-estimate(reference[metric],indices)
            dlo,dhi=np.quantile(dif,[.025,.975],method='linear')
            delta.append(base|dict(k=10,metric=metric,reference='unmasked / archived_weighted_score / shared_IFEP_required',
                                   estimate_difference=point-estimate(reference[metric]),lower_025=float(dlo),upper_975=float(dhi),
                                   bootstrap_draws=DRAWS,seed=SEED))
        for src in ids:
            f=frame[frame.source_pfep_id.ne(src)]
            for metric,x in measures(f).items():
                leave_source.append(base|dict(omitted_source=src,metric=metric,value=estimate(x),
                                              sources_n=len(f),endpoint_pairs_n=int(f.attested_endpoints_n.sum())))
        for inv in sorted(frame.inventory.unique()):
            f=frame[frame.inventory.ne(inv)]
            for metric,x in measures(f).items():
                leave_inventory.append(base|dict(omitted_inventory=inv,metric=metric,value=estimate(x),
                                                 sources_n=len(f),endpoint_pairs_n=int(f.attested_endpoints_n.sum())))
    write_csv(data/'robustness_retrieval_resampling.csv',ci)
    write_csv(data/'robustness_retrieval_paired_differences.csv',delta)
    write_csv(data/'robustness_leave_one_source.csv',leave_source)
    write_csv(data/'robustness_leave_one_inventory.csv',leave_inventory)
    write_csv(data/'robustness_all_28_configs_by_source.csv',full)
    return ci,delta


def record_fixtures(root:Path):
    observed=json.loads((root/'specifications/observed_H_1_6_3.json').read_text())
    schema=json.loads((root/'specifications/screening_record.schema.json').read_text())
    cases=[]
    def add(name,record,expected):
        cases.append((name,record,expected))
    r=copy.deepcopy(observed);r['relations'][0]['targets']='Bu13';add('target_field_wrong_type',r,'format.type')
    r=copy.deepcopy(observed);r['adoption']={'status':'recorded','authority':'SYNTHETIC TEST ONLY','decision_date':'2026-02-30','adopted_relation_ids':['absent'],'justification':'Synthetic test.'};add('invalid_adoption_calendar_date',r,'format.date')
    r=copy.deepcopy(observed);r['relations'].append(copy.deepcopy(r['relations'][0]));add('duplicate_relation_id',r,'application.duplicate_relation')
    r=copy.deepcopy(observed);r['relations'][0]['source']['identifier']='synthetic_other';add('source_key_mismatch',r,'application.source_key')
    adoption={'status':'recorded','authority':'SYNTHETIC TEST ONLY','decision_date':'2026-10-17',
              'adopted_relation_ids':['absent'],'justification':'Synthetic fault-injection fixture, not an archive observation.'}
    r=copy.deepcopy(observed);r['adoption']=copy.deepcopy(adoption);add('missing_adopted_relation',r,'application.adoption_reference')
    r=copy.deepcopy(observed);r['adoption']=copy.deepcopy(adoption);r['adoption']['adopted_relation_ids']=[r['relations'][0]['relation_id']]
    add('adopted_scope_unrecorded',copy.deepcopy(r),'application.adopted_scope')
    r['relations'][0]['targets']=[];add('adopted_target_empty',r,'application.adopted_target')
    r=copy.deepcopy(observed);r['relations'][0]['scope']['status']='specified';add('specified_scope_empty',r,'application.specified_scope')
    r=copy.deepcopy(observed);r['retrieval_leads']=[{'candidate':copy.deepcopy(r['relations'][0]['targets'][0]),
         'origin':'analytical_retrieval','method_id':'SYNTHETIC_TEST','rank':2,'score':.2,'threshold':None,
         'eligible_pool_size':1,'missing_source_fields':[],'query_fingerprint':'synthetic'}];add('rank_outside_eligible_pool',r,'application.retrieval_rank')
    r=copy.deepcopy(observed);del r['screening']['reason'];add('required_reason_missing',r,'format.required')
    r=copy.deepcopy(observed);r['adoption']['adopted_relation_ids']=[r['relations'][0]['relation_id']];add('unrecorded_adoption_with_adopted_ids',r,'application.unrecorded_adoption')
    r=copy.deepcopy(observed);r['stage_changes']=[{'relation_id':r['relations'][0]['relation_id'],'from_stage':'SR-Site','to_stage':'SYNTHETIC_NEXT_STAGE','disposition':'superseded','successor':None,'reason':'Synthetic missing-successor test.'}];add('superseded_without_successor',r,'application.stage_successor')
    r=copy.deepcopy(observed);r['stage_changes']=[{'relation_id':r['relations'][0]['relation_id'],'from_stage':'SR-Site','to_stage':'SYNTHETIC_NEXT_STAGE','disposition':'superseded','successor':copy.deepcopy(r['relations'][0]['targets'][0]),'reason':'Synthetic wrong-stage test.'}];add('successor_stage_mismatch',r,'application.successor_stage')
    results=[]
    fixtures_dir=root/'tests/synthetic_fixtures';fixtures_dir.mkdir(parents=True, exist_ok=True)
    control=check_record(observed,schema)
    assert control['format_valid'] and not control['application_issues'] and control['technical_review_tasks']
    results.append(dict(fixture='observed_control',fixture_kind='observed_example',expected='format_valid; no application issue; unresolved technical tasks retained',
                        passed=True,observed_codes='; '.join(x['code'] for x in control['technical_review_tasks'])))
    for name,record,expected in cases:
        result=check_record(record,schema)
        codes={x['code'] for k in ('format_issues','application_issues') for x in result[k]}
        passed=expected in codes
        results.append(dict(fixture=name,fixture_kind='synthetic_fault_not_archive_data',expected=expected,
                            passed=passed,observed_codes='; '.join(sorted(codes))))
        (fixtures_dir/f'{name}.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n')
        if not passed: raise AssertionError((name,expected,result))
    write_csv(root/'data/robustness_record_fixture_results.csv',results)
    return results


def main(root=ROOT):
    start=time.perf_counter();data=root/'data'
    inputs=['record_endpoint_metrics_by_source.csv','retrieval_rank_comparison_pairs.csv','retrieval_benchmark_query_texts.csv',
            'pfep_relevance_population_1671.csv','not_relevant_370_normalized.csv','coverage_evidence_200.csv']
    hashes={n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in inputs}
    metrics,sources,timing=bm25_pairs(data)
    ci,delta=summarize_sensitivity(data,sources)
    fixtures=record_fixtures(root)
    assert hashes=={n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in inputs},'Input mutated'
    summary={'version':VERSION,'nature':'Retrospective reanalysis and synthetic software verification; no independent expert or field validation',
             'bm25_configs_n':4,'original_configs_n':24,'all_configs_n':28,'bm25':timing,
             'resampling':{'seed':SEED,'draws':DRAWS,'resampling_unit':'source with entire endpoint set; identical draws for paired methods',
                           'inference_limit':'Purposive, clustered internal benchmark: intervals are conditional sensitivity summaries, not population generalization.'},
             'synthetic_faults_n':len(fixtures)-1,'synthetic_faults_flagged_n':sum(r['passed'] for r in fixtures[1:]),
             'control_preserves_review_tasks':True,'input_sha256':hashes,
             'total_elapsed_seconds':time.perf_counter()-start,
             'python':sys.version,'platform':platform.platform(),'cpu':platform.processor(), 'analysis_stage':'retrospective descriptive analysis'}
    (data/'robustness_validation_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,default=ROOT)
    main(parser.parse_args().package)
