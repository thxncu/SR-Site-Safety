#!/usr/bin/env python3
"""Compute endpoint-set metrics, source review tasks and worked-case records.

Inputs are source-located documentary interpretations and fixed retrieval ranks.
Run from any directory: python code/compute_record_analysis.py [--package PATH]
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CONFIG = ('query_variant', 'model', 'eligibility_rule')
K_VALUES = (1, 5, 10, 20)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f'No rows to write: {path}')
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def is_one(value: str) -> bool:
    return str(value).strip() in ('1', '1.0', 'True', 'true')


def aggregate_endpoints(rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        groups[tuple(row[c] for c in CONFIG)].append(row)
    summary, source_rows = [], []
    for config, entries in sorted(groups.items()):
        by_source: dict[str, list] = defaultdict(list)
        seen = set()
        for row in entries:
            pair = (row['source_pfep_id'], row['verified_endpoint_id'])
            if pair in seen:
                raise ValueError(f'Duplicate endpoint pair for {config}: {pair}')
            seen.add(pair)
            by_source[pair[0]].append(row)
        n_sources, n_endpoints = len(by_source), len(entries)
        n_multi = sum(len(v) > 1 for v in by_source.values())
        eligible_n = sum(is_one(r['endpoint_eligible']) for r in entries)
        feasible_sets = sum(all(is_one(r['endpoint_eligible']) for r in v) for v in by_source.values())
        for k in K_VALUES:
            hits = recovered = complete = multi_complete = 0
            macro = 0.0
            for source, pairs in sorted(by_source.items()):
                recovered_ids = [r['verified_endpoint_id'] for r in pairs
                                 if is_one(r['endpoint_eligible']) and r['endpoint_rank']
                                 and float(r['endpoint_rank']) <= k]
                count, n = len(recovered_ids), len(pairs)
                hits += count > 0
                recovered += count
                complete += count == n
                multi_complete += n > 1 and count == n
                macro += count / n
                source_rows.append(dict(zip(CONFIG, config)) | {
                    'k': k, 'source_pfep_id': source,
                    'attested_endpoints_n': n, 'recovered_endpoints_n': count,
                    'hit': int(count > 0), 'complete_set': int(count == n),
                    'recovered_endpoint_ids': '; '.join(sorted(recovered_ids)),
                    'not_recovered_endpoint_ids': '; '.join(sorted(
                        r['verified_endpoint_id'] for r in pairs
                        if r['verified_endpoint_id'] not in recovered_ids)),
                })
            summary.append(dict(zip(CONFIG, config)) | {
                'k': k, 'sources_n': n_sources, 'attested_endpoints_n': n_endpoints,
                'multi_endpoint_sources_n': n_multi,
                'eligible_endpoints_n': eligible_n,
                'all_endpoints_eligible_sources_n': feasible_sets,
                'endpoint_recall_ceiling': eligible_n / n_endpoints,
                'complete_set_ceiling': feasible_sets / n_sources,
                'hit_sources_n': hits, 'hit_fraction': hits / n_sources,
                'recovered_endpoints_n': recovered,
                'endpoint_recall_micro': recovered / n_endpoints,
                'endpoint_recall_macro': macro / n_sources,
                'complete_sets_n': complete, 'complete_set_fraction': complete / n_sources,
                'multi_endpoint_complete_sets_n': multi_complete,
                'multi_endpoint_complete_set_fraction': multi_complete / n_multi if n_multi else '',
            })
    return summary, source_rows


def review_queue(rows: list[dict[str, str]]) -> tuple[list[dict], dict]:
    queue = []
    for r in rows:
        n = int(r['n_unique_resolved_destinations'])
        identity_task = ('identify_or_disambiguate_destination' if n == 0 else
                         'review_single_destination_scope' if n == 1 else
                         'review_distributed_destination_scope')
        queue.append({
            'pfep_id': r['pfep_id'], 'pfep_title': r['pfep_name'],
            'project_letter': r['project_letter'], 'formal_reason': r['reason'],
            'documentary_class': r['documentary_class'],
            'resolved_destinations_n': n, 'identity_review_task': identity_task,
            'historical_association_review': int(is_one(r['historical_association_present'])),
            'lookup_qualification_review': int(is_one(r['reference_resolution_issue_present'])),
            'retained_link_status_review': int(is_one(r['status_conflict_present'])),
            'relation_specific_SR_Site_adoption_observed': int(is_one(r['current_skb_adoption_documented'])),
            'earlier_stage_adoption_observed': int(is_one(r['skb_adoption_documented']) and not is_one(r['current_skb_adoption_documented'])),
            'additional_scope_rationale_text_observed': int(is_one(r['skb_discussion_scope_rationale_present'])),
            'screening_decision_preserved': int(is_one(r['formal_reason_coverage_assertion'])),
            'technical_adequacy': 'not_independently_assessed',
            'queue_status': 'research_derived_review_task_not_an_adopted_decision',
        })
    summaries = {'sources_n': len(queue), 'identity_tasks': dict(Counter(r['identity_review_task'] for r in queue))}
    for key in ('historical_association_review', 'lookup_qualification_review',
                'retained_link_status_review', 'relation_specific_SR_Site_adoption_observed',
                'earlier_stage_adoption_observed', 'additional_scope_rationale_text_observed',
                'screening_decision_preserved'):
        summaries[key] = sum(r[key] for r in queue)
    return queue, summaries


def branch_summary(rows: list[dict], edge_rows: list[dict]) -> list[dict]:
    branches = ('I 126', 'I 058', 'I 061', 'I 273')
    all_source_pairs = {(r['pfep_id'], r['sr_id']) for r in edge_rows if r['pfep_id'] in branches}
    raw_pairs = {(r['NEA PROJECT FEP ID'].strip(), r['SRSITE FEP ID'].strip()) for r in rows}
    if raw_pairs != all_source_pairs:
        raise ValueError('Technical-case rows do not cover exactly the four branch pair sets in the full graph.')
    out = []
    for branch in branches:
        selected = [r for r in rows if r['NEA PROJECT FEP ID'].strip() == branch]
        out.append({
            'source_pfep_id': 'I 165', 'imported_endpoint_id': branch,
            'handling_rows_n': len(selected),
            'unique_SR_Site_targets_n': len({r['SRSITE FEP ID'] for r in selected}),
            'handled_text_rows_n': sum(bool(r.get('ASPECTS OF NEA FEP HANDLED', '').strip()) for r in selected),
            'unhandled_text_rows_n': sum(bool(r.get('UNHANDLED ASPECTS BECAUSE', '').strip()) for r in selected),
            'comment_rows_n': sum(bool(r.get('COMMENTS', '').strip()) for r in selected),
            'source_record_ids': '; '.join(r['source_record_id'] for r in selected),
            'SR_Site_target_ids': '; '.join(r['SRSITE FEP ID'] for r in selected),
            'interpretation_limit': 'Downstream association and annotation inventory; not adopted transitive coverage.',
        })
    return out


def source_aspects(rows: list[dict[str, str]]) -> list[dict]:
    source = next(r for r in rows if r['pfep_id'] == 'H 1.6.3')
    text = source['imported_description_raw']
    names = ('metal corrosion', 'physico-chemical degradation of concrete',
             'physico-chemical degradation of waste-forms',
             'microbial degradation of organic wastes', 'gas production',
             'complex formation', 'colloid production', 'radionuclide solubility',
             'sorption processes', 'speciation')
    result = []
    for i, name in enumerate(names, 1):
        marker = re.search(r'(?<![0-9])' + str(i) + r'\)\s*' + re.escape(name), text)
        if marker is None:
            raise ValueError(f'Missing enumerated source aspect {i}: {name}')
        start = text.index(name, marker.start())
        result.append({'source_pfep_id': 'H 1.6.3', 'aspect_number': i,
                       'source_aspect_literal': name, 'source_field': 'imported_description_raw',
                       'span_start': start, 'span_end': start + len(name),
                       'observed_source_level_target': 'Bu13',
                       'aspect_specific_target': '',
                       'scope_status': 'not_assigned_by_this_documentary_reconstruction',
                       'source_context': 'Imported intermediate-level-waste thermal-pulse description',
                       'followup': 'Determine applicability to KBS-3; record treatment or justified exclusion.'})
    return result


def main(package: Path) -> dict:
    data = package / 'data'
    inputs = ['retrieval_rank_comparison_pairs.csv', 'retrieval_rank_comparison_summary.csv',
              'retrieval_main_table_seven_rows.csv', 'coverage_evidence_200.csv',
              'technical_case_handling_rows.json', 'pfep_srsite_network_edges.csv']
    metrics, source_rows = aggregate_endpoints(read_csv(data / inputs[0]))
    assert len(metrics) == 24 * len(K_VALUES)
    assert all(r['sources_n'] == 18 and r['attested_endpoints_n'] == 42 for r in metrics)
    existing = {tuple(r[c] for c in CONFIG): r for r in read_csv(data / inputs[1])}
    for r in metrics:
        old = existing[tuple(r[c] for c in CONFIG)]
        assert r['hit_sources_n'] == int(old[f"hit_at_{r['k']}_n"])
        assert abs(r['endpoint_recall_micro'] - float(old[f"verified_endpoint_recall_at_{r['k']}_micro"])) < 1e-10
    write_csv(data / 'record_endpoint_metrics_24_configs.csv', metrics)
    write_csv(data / 'record_endpoint_metrics_by_source.csv', source_rows)
    index = {(tuple(r[c] for c in CONFIG), r['k']): r for r in metrics}
    table_rows = []
    for old in read_csv(data / inputs[2]):
        config = tuple(old[c] for c in CONFIG)
        new = {'comparison_label': old['comparison_label']} | index[(config, 10)]
        new['hit_at_1_n'] = index[(config, 1)]['hit_sources_n']
        new['hit_at_5_n'] = index[(config, 5)]['hit_sources_n']
        table_rows.append(new)
    write_csv(data / 'record_retrieval_main_table.csv', table_rows)
    cohort = [r for r in read_csv(data / inputs[3]) if r['project_letter'] != 'N']
    assert len(cohort) == 55
    queue, queue_summary = review_queue(cohort)
    write_csv(data / 'record_review_queue_55.csv', queue)
    aspects = source_aspects(cohort)
    write_csv(data / 'record_H163_source_aspects.csv', aspects)
    branches = branch_summary(json.loads((data / inputs[4]).read_text()), read_csv(data / inputs[5]))
    write_csv(data / 'record_I165_branch_inventory.csv', branches)
    result = {'version': '3.1.0', 'basis': 'Existing source-derived data; no new expert labels or safety calculations.',
              'cohort': queue_summary, 'I165_branches': branches, 'H163_enumerated_aspects_n': len(aspects),
              'inputs_sha256': {f: hashlib.sha256((data / f).read_bytes()).hexdigest() for f in inputs},
              'tests': {'24_configurations_reconstructed': True,
                        'existing_Hit_and_recall_reproduced': True,
                        'four_branch_sets_match_full_handling_graph': True}}
    (data / 'record_analysis_summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    main(args.package.resolve())
