#!/usr/bin/env python3
"""Reproduce auxiliary retrieval from source-based documentary inputs.

The script never overwrites the documentary classifications or source relations.
Its threshold-dependent candidates and failures are separate search outcomes.
"""
from pathlib import Path
import argparse
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from traceability_semantics import (
    BASELINE_WEIGHTS, SOURCE_FIELDS, CANDIDATE_FIELDS, WORD_OPTIONS, CHAR_OPTIONS,
    build_components, load_population, clean, ifeps, score, rank_candidates,
    conditional_outcome, benchmark_rank,
)

THRESHOLDS = (0.30, 0.34, 0.38, 0.42, 0.46, 0.50)
PRIMARY_THRESHOLD = 0.34
PRIMARY_MODEL = "baseline_text_fields"
PRIMARY_GATE = "shared_IFEP_required"
OUTCOMES = ("candidate_at_or_above_threshold", "best_eligible_below_threshold",
            "no_eligible_candidate")
MODEL_DESCRIPTIONS = {
    "baseline_text_fields": "Source title excluded from source TF-IDF; candidate title included; original four score terms.",
    "title_only_ablation": "Title-only ranking with score 0.25*T + 0.15*f; original title and compatibility coefficients retained without renormalisation.",
    "missing_text_title_fallback": "Only empty source-text queries are transformed from their title using the already fitted vectorisers; nonempty queries and the candidate representation are unchanged.",
}


def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def boolean_column(frame, name):
    if name not in frame:
        raise ValueError(f"Required boolean input column is absent: {name}")
    values = frame[name].map(clean).str.lower()
    mapping = {"1": True, "0": False, "true": True, "false": False}
    if not values.isin(mapping).all():
        raise ValueError(f"Column {name} must contain explicit 0/1 or true/false values")
    return values.map(mapping).astype(bool)


def load_documentary_inputs(decision_path, relation_path, source_ids):
    decisions = read_csv(decision_path)
    required = {"pfep_id", "documentary_class", "documentary_unresolved"}
    if not required.issubset(decisions.columns):
        raise ValueError(f"Decision table requires {sorted(required)}")
    if not decisions.pfep_id.is_unique or set(decisions.pfep_id) != set(source_ids):
        raise ValueError("Decision table must identify every covered-elsewhere source exactly once")
    decisions["documentary_unresolved"] = boolean_column(decisions, "documentary_unresolved")
    if "no_resolved_relevant_destination" in decisions:
        decisions["no_resolved_relevant_destination"] = boolean_column(decisions, "no_resolved_relevant_destination")
    decisions = decisions.set_index("pfep_id").loc[list(source_ids)].reset_index()
    relations = read_csv(relation_path)
    required = {"source_pfep_id", "target_id", "target_type", "origin_layer", "source_field",
                "relation_semantics", "evidence_span", "direction_valid", "benchmark_eligible",
                "reference_verified"}
    if not required.issubset(relations.columns):
        raise ValueError(f"Relation table lacks {sorted(required - set(relations.columns))}")
    for name in ("direction_valid", "benchmark_eligible", "reference_verified"):
        relations[name] = boolean_column(relations, name)
    selected = relations.benchmark_eligible
    if not relations.loc[selected, "direction_valid"].all():
        raise ValueError("A benchmark endpoint lacks a valid reference direction")
    if not relations.loc[selected, "reference_verified"].all():
        raise ValueError("A benchmark endpoint is not marked as a source-verified reference")
    if not relations.loc[selected, "target_type"].str.upper().eq("PFEP").all():
        raise ValueError("Benchmark endpoints must be PFEP identifiers")
    for field in ("origin_layer", "source_field", "relation_semantics", "evidence_span"):
        if relations.loc[selected, field].map(clean).eq("").any():
            raise ValueError(f"A benchmark endpoint is missing its {field}")
    if not set(relations.loc[selected, "source_pfep_id"]).issubset(set(source_ids)):
        raise ValueError("A benchmark source lies outside the coverage source population")
    return decisions, relations


def text_availability(comp, decisions):
    rows = []
    state = decisions.set_index("pfep_id") if decisions is not None else None
    for i, record in comp.source.iterrows():
        row = {"pfep_id": record.pfep_id, "project_letter": record.project_letter,
               "source_title": clean(record.pfep_name),
               "source_text_empty": int(comp.source_text_empty[i]),
               "source_text_characters": len(comp.source_text.iloc[i]),
               "source_text_words": len(comp.source_text.iloc[i].split()),
               "word_vector_nonzero_features": int(comp.word_nonzero_features[i]),
               "character_vector_nonzero_features": int(comp.character_nonzero_features[i]),
               "source_ifep_count": len(ifeps(record.international_fep_numbers_all))}
        for field in ("pfep_name", *SOURCE_FIELDS):
            row[field + "_empty"] = int(not clean(record[field]))
        row["original_inventory_text_empty"] = int(not clean(clean(record.pfep_description) + " " + clean(record.pfep_comments)))
        row["skb_decision_text_empty"] = int(not clean(clean(record.comments_needs_discussion) + " " + clean(record.assessment_basis_comment)))
        if state is not None:
            row["documentary_class"] = state.loc[record.pfep_id, "documentary_class"]
            row["documentary_unresolved"] = int(state.loc[record.pfep_id, "documentary_unresolved"])
            if "no_resolved_relevant_destination" in state:
                row["no_resolved_relevant_destination"] = int(state.loc[record.pfep_id, "no_resolved_relevant_destination"])
        rows.append(row)
    records = pd.DataFrame(rows)
    missing = []
    scopes = [("covered_elsewhere_sources", comp.source.index.tolist())]
    if state is not None:
        scopes.append(("documentary_unresolved_sources", np.flatnonzero(decisions.documentary_unresolved).tolist()))
    for scope, indices in scopes:
        sample = comp.source.loc[indices]
        for inventory in ["All", *sorted(sample.project_letter.unique())]:
            ids = sample.index if inventory == "All" else sample[sample.project_letter.eq(inventory)].index
            n = len(ids)
            fields = {field: comp.source.loc[ids, field].map(clean).eq("")
                      for field in ("pfep_name", *SOURCE_FIELDS)}
            fields["combined_source_text"] = comp.source_text.loc[ids].eq("")
            fields["IFEP_identifier_set"] = comp.source.loc[ids, "international_fep_numbers_all"].map(ifeps).map(len).eq(0)
            fields["word_TFIDF_vector"] = pd.Series(comp.word_nonzero_features[ids] == 0)
            fields["character_TFIDF_vector"] = pd.Series(comp.character_nonzero_features[ids] == 0)
            for field, absent in fields.items():
                count = int(absent.sum())
                missing.append({"scope": scope, "project_letter": inventory, "field": field,
                                "n_records": n, "missing_or_zero_n": count,
                                "present_or_nonzero_n": n - count,
                                "missing_or_zero_fraction": count / n if n else np.nan})
    for inventory in ["All", *sorted(comp.relevant.project_letter.unique())]:
        selected = comp.relevant if inventory == "All" else comp.relevant[comp.relevant.project_letter.eq(inventory)]
        n = len(selected)
        fields = {field: selected[field].map(clean).eq("") for field in CANDIDATE_FIELDS}
        fields["combined_candidate_text"] = comp.candidate_text.loc[selected.index].eq("")
        fields["IFEP_identifier_set"] = selected.international_fep_numbers_all.map(ifeps).map(len).eq(0)
        for field, absent in fields.items():
            count = int(absent.sum())
            missing.append({"scope": "relevant_candidates", "project_letter": inventory,
                            "field": field, "n_records": n, "missing_or_zero_n": count,
                            "present_or_nonzero_n": n - count,
                            "missing_or_zero_fraction": count / n if n else np.nan})
    return records, pd.DataFrame(missing)


def search_results(comp, decisions, model_scores):
    ids = comp.relevant.pfep_id.tolist()
    top_rows, ranking_rows, orders = [], [], {}
    for model, scores in model_scores.items():
        for gate, required in ((PRIMARY_GATE, True), ("no_IFEP_eligibility_filter", False)):
            for i, record in comp.source.iterrows():
                order = rank_candidates(scores[i], comp.shared_ifep[i], ids, {record.pfep_id}, required)
                orders[model, gate, record.pfep_id] = order
                j = order[0] if order else None
                result = conditional_outcome(order, scores[i], PRIMARY_THRESHOLD)
                failure_detail = ""
                if result == "no_eligible_candidate":
                    failure_detail = "source_has_no_IFEP_identifier" if not ifeps(record.international_fep_numbers_all) else "no_relevant_candidate_shares_IFEP"
                elif result == "best_eligible_below_threshold":
                    failure_detail = "source_text_empty" if comp.source_text_empty[i] else "source_text_present"
                row = {"source_pfep_id": record.pfep_id, "source_pfep_name": record.pfep_name,
                       "project_letter": record.project_letter,
                       "documentary_class": decisions.iloc[i].documentary_class,
                       "documentary_unresolved": int(decisions.iloc[i].documentary_unresolved),
                       "model": model, "eligibility_rule": gate,
                       "source_text_empty": int(comp.source_text_empty[i]),
                       "source_ifep_count": len(ifeps(record.international_fep_numbers_all)),
                       "relevant_pool_n": len(ids), "eligible_candidate_n": len(order),
                       "top_target_id": ids[j] if j is not None else "",
                       "top_target_name": comp.relevant.iloc[j].pfep_name if j is not None else "",
                       "top_score": float(scores[i, j]) if j is not None else np.nan,
                       "top_title_similarity": float(comp.title[i, j]) if j is not None else np.nan,
                       "top_shared_ifep_n": int(comp.shared_ifep[i, j]) if j is not None else 0,
                       "threshold": PRIMARY_THRESHOLD, "search_outcome": result,
                       "failure_detail": failure_detail,
                       "title_used_as_missing_text_fallback": int(model == "missing_text_title_fallback" and comp.source_text_empty[i])}
                if "no_resolved_relevant_destination" in decisions:
                    row["no_resolved_relevant_destination"] = int(decisions.iloc[i].no_resolved_relevant_destination)
                top_rows.append(row)
                for rank, k in enumerate(order[:10], 1):
                    ranking_rows.append({"source_pfep_id": record.pfep_id,
                        "project_letter": record.project_letter,
                        "documentary_unresolved": int(decisions.iloc[i].documentary_unresolved),
                        "model": model, "eligibility_rule": gate, "rank": rank,
                        "target_id": ids[k], "target_name": comp.relevant.iloc[k].pfep_name,
                        "score": float(scores[i, k]),
                        "word_similarity": float((comp.fallback_word if model == "missing_text_title_fallback" else comp.word)[i, k]),
                        "character_similarity": float((comp.fallback_character if model == "missing_text_title_fallback" else comp.character)[i, k]),
                        "title_similarity": float(comp.title[i, k]),
                        "shared_ifep_n": int(comp.shared_ifep[i, k]),
                        "source_text_empty": int(comp.source_text_empty[i])})
    return pd.DataFrame(top_rows), pd.DataFrame(ranking_rows), orders


def threshold_sensitivity(results):
    rows = []
    unresolved = results[results.documentary_unresolved.eq(1)]
    for (model, gate), full in unresolved.groupby(["model", "eligibility_rule"], sort=False):
        for label, selected in (("All", full), ("Project N", full[full.project_letter.eq("N")]),
                                ("Other inventories", full[~full.project_letter.eq("N")])):
            for threshold in THRESHOLDS:
                empty_pool = selected.eligible_candidate_n.eq(0)
                retained = ~empty_pool & selected.top_score.ge(threshold)
                below = ~empty_pool & ~retained
                rows.append({"scope": label, "model": model, "eligibility_rule": gate,
                             "score_threshold": threshold, "documentary_unresolved_n": len(selected),
                             "candidate_at_or_above_threshold_n": int(retained.sum()),
                             "best_eligible_below_threshold_n": int(below.sum()),
                             "no_eligible_candidate_n": int(empty_pool.sum()),
                             "below_threshold_empty_source_text_n": int((below & selected.source_text_empty.eq(1)).sum()),
                             "below_threshold_nonempty_source_text_n": int((below & selected.source_text_empty.eq(0)).sum()),
                             "no_eligible_missing_source_IFEP_n": int((empty_pool & selected.source_ifep_count.eq(0)).sum()),
                             "no_eligible_despite_source_IFEP_n": int((empty_pool & selected.source_ifep_count.gt(0)).sum()),
                             "title_similarity_threshold_if_title_only": (threshold - 0.15) / 0.25 if model == "title_only_ablation" and gate == PRIMARY_GATE else np.nan})
    return pd.DataFrame(rows)


def benchmark_sets(relations, candidate_ids):
    candidate_ids = set(candidate_ids)
    strict = relations[relations.benchmark_eligible].copy()
    if not set(strict.target_id).issubset(candidate_ids):
        raise ValueError("A strict benchmark endpoint is absent from the relevant candidate pool")
    broader = relations[relations.reference_verified & relations.direction_valid
                        & relations.target_type.str.upper().eq("PFEP")
                        & relations.target_id.isin(candidate_ids)].copy()
    return {"strict_source_endpoints": strict, "broader_directional_references": broader}


def benchmark_results(comp, relations, model_scores, orders):
    ids = comp.relevant.pfep_id.tolist()
    index_of = {identifier: i for i, identifier in enumerate(comp.source.pfep_id)}
    cases, summaries, gold_rows = [], [], []
    sets = benchmark_sets(relations, ids)
    for scope, endpoints in sets.items():
        groups = list(endpoints.groupby("source_pfep_id", sort=True))
        for source_id, evidence in groups:
            if source_id not in index_of:
                continue
            for _, row in evidence.iterrows():
                gold_rows.append({"benchmark_scope": scope, **row.to_dict()})
        for model, scores in model_scores.items():
            for gate in (PRIMARY_GATE, "no_IFEP_eligibility_filter"):
                selected_cases = []
                for source_id, evidence in groups:
                    if source_id not in index_of:
                        continue
                    i = index_of[source_id]
                    order = orders[model, gate, source_id]
                    targets = set(evidence.target_id)
                    best, eligible = benchmark_rank(order, ids, targets)
                    if not order:
                        status = "no_eligible_candidate"
                    elif not eligible:
                        status = "no_source_endpoint_eligible"
                    elif best > 10:
                        status = "source_endpoint_beyond_rank_10"
                    else:
                        status = "source_endpoint_within_rank_10"
                    row = {"benchmark_scope": scope, "source_pfep_id": source_id,
                           "project_letter": comp.source.iloc[i].project_letter,
                           "source_pfep_name": comp.source.iloc[i].pfep_name,
                           "model": model, "eligibility_rule": gate,
                           "source_text_empty": int(comp.source_text_empty[i]),
                           "relevant_pool_n": len(ids), "eligible_candidate_n": len(order),
                           "source_endpoint_n": len(targets),
                           "source_endpoint_ids": "; ".join(sorted(targets)),
                           "eligible_source_endpoint_n": len(eligible),
                           "eligible_source_endpoint_ids": "; ".join(sorted(eligible)),
                           "source_endpoint_ranks": json.dumps(eligible, sort_keys=True),
                           "best_source_endpoint_rank": best if best is not None else np.nan,
                           "hit_at_1": int(best is not None and best <= 1),
                           "hit_at_5": int(best is not None and best <= 5),
                           "hit_at_10": int(best is not None and best <= 10),
                           "benchmark_outcome": status,
                           "origin_layers": "; ".join(sorted(set(evidence.origin_layer))),
                           "source_fields": "; ".join(sorted(set(evidence.source_field))),
                           "relation_semantics": "; ".join(sorted(set(evidence.relation_semantics)))}
                    cases.append(row)
                    selected_cases.append(row)
                frame = pd.DataFrame(selected_cases)
                n = len(frame)
                summary = {"benchmark_scope": scope, "model": model, "eligibility_rule": gate,
                           "n_source_cases": n, "n_Project_N_cases": int(frame.project_letter.eq("N").sum()) if n else 0,
                           "n_empty_source_text_cases": int(frame.source_text_empty.sum()) if n else 0,
                           "eligible_candidate_n_min": int(frame.eligible_candidate_n.min()) if n else 0,
                           "eligible_candidate_n_max": int(frame.eligible_candidate_n.max()) if n else 0,
                           "cases_with_eligible_endpoint_n": int(frame.eligible_source_endpoint_n.gt(0).sum()) if n else 0,
                           "no_eligible_candidate_n": int(frame.eligible_candidate_n.eq(0).sum()) if n else 0,
                           "no_endpoint_eligible_n": int(frame.eligible_source_endpoint_n.eq(0).sum()) if n else 0,
                           "median_best_rank_when_endpoint_eligible": float(frame.best_source_endpoint_rank.median()) if n and frame.best_source_endpoint_rank.notna().any() else None}
                for k in (1, 5, 10):
                    hits = int(frame[f"hit_at_{k}"].sum()) if n else 0
                    summary[f"hit_at_{k}_n"] = hits
                    summary[f"hit_at_{k}_fraction"] = hits / n if n else None
                summaries.append(summary)
    return pd.DataFrame(cases), pd.DataFrame(summaries), pd.DataFrame(gold_rows)


def model_comparison(results):
    selected = results[results.documentary_unresolved.eq(1) & results.eligibility_rule.eq(PRIMARY_GATE)]
    baseline = selected[selected.model.eq(PRIMARY_MODEL)].set_index("source_pfep_id")
    rows = []
    for model, frame in selected.groupby("model", sort=False):
        for scope, group in (("All", frame), ("Project N", frame[frame.project_letter.eq("N")]),
                             ("Other inventories", frame[~frame.project_letter.eq("N")])):
            with_pool = group[group.eligible_candidate_n.gt(0)]
            same = sum(r.top_target_id == baseline.loc[r.source_pfep_id, "top_target_id"]
                       for r in with_pool.itertuples(index=False))
            row = {"scope": scope, "model": model, "documentary_unresolved_n": len(group),
                   "sources_with_eligible_pool_n": len(with_pool),
                   "same_leading_target_as_baseline_n": same,
                   "source_text_empty_n": int(group.source_text_empty.sum()),
                   "threshold": PRIMARY_THRESHOLD}
            row.update({outcome + "_n": int(group.search_outcome.eq(outcome).sum()) for outcome in OUTCOMES})
            rows.append(row)
    return pd.DataFrame(rows)


def weight_sensitivity(comp, decisions, relations):
    ids = comp.relevant.pfep_id.tolist()
    indices = np.flatnonzero(decisions.documentary_unresolved)
    strict = benchmark_sets(relations, ids)["strict_source_endpoints"]
    gold = strict.groupby("source_pfep_id").target_id.apply(set).to_dict()
    index_of = {p: i for i, p in enumerate(comp.source.pfep_id)}
    settings = {
        "Baseline": BASELINE_WEIGHTS,
        "Equal weights": (0.25, 0.25, 0.25, 0.25),
        "Text weighted": (0.45, 0.30, 0.15, 0.10),
        "Title weighted": (0.25, 0.15, 0.45, 0.15),
        "Compatibility removed and other terms renormalised": (0.35 / 0.85, 0.25 / 0.85, 0.25 / 0.85, 0.0),
    }
    baseline_top = {}
    rows = []
    for name, weights in settings.items():
        scores = score(comp.word, comp.character, comp.title, comp.shared_ifep, weights)
        tops, has_pool, retained = {}, 0, 0
        equivalent_cutoff = (PRIMARY_THRESHOLD - 0.15) / 0.85 if weights[-1] == 0.0 else None
        retained_equivalent = 0 if equivalent_cutoff is not None else None
        for i in indices:
            source_id = comp.source.iloc[i].pfep_id
            order = rank_candidates(scores[i], comp.shared_ifep[i], ids, {source_id}, True)
            if order:
                has_pool += 1
                j = order[0]
                tops[source_id] = ids[j]
                retained += float(scores[i, j]) >= PRIMARY_THRESHOLD
                if equivalent_cutoff is not None:
                    retained_equivalent += float(scores[i, j]) >= equivalent_cutoff
        if name == "Baseline":
            baseline_top = tops.copy()
        ranks = []
        for source_id, targets in gold.items():
            i = index_of[source_id]
            order = rank_candidates(scores[i], comp.shared_ifep[i], ids, {source_id}, True)
            best, _ = benchmark_rank(order, ids, targets)
            ranks.append(best)
        rows.append({"weight_set": name, "weights_word_character_title_compatibility": "/".join(f"{w:.10g}" for w in weights),
                     "documentary_unresolved_n": len(indices), "sources_with_eligible_pool_n": has_pool,
                     "same_leading_target_as_baseline_n": sum(target == baseline_top.get(source_id) for source_id, target in tops.items()),
                     "numeric_cutoff": PRIMARY_THRESHOLD, "candidates_at_numeric_cutoff_n": int(retained),
                     "algebraically_equivalent_baseline_cutoff": equivalent_cutoff,
                     "candidates_at_equivalent_cutoff_n": retained_equivalent,
                     "strict_benchmark_source_n": len(ranks),
                     "strict_benchmark_hit_at_1_n": sum(r is not None and r <= 1 for r in ranks),
                     "strict_benchmark_hit_at_5_n": sum(r is not None and r <= 5 for r in ranks),
                     "strict_benchmark_hit_at_10_n": sum(r is not None and r <= 10 for r in ranks)})
    return pd.DataFrame(rows)


def specifications(comp):
    return {
        "purpose": "Auxiliary source-record retrieval, separate from documentary provenance classification",
        "source_text_fields": list(SOURCE_FIELDS), "candidate_text_fields": list(CANDIDATE_FIELDS),
        "source_title_in_baseline_TFIDF": False, "candidate_title_in_TFIDF": True,
        "TFIDF_fit_corpus": "All covered-elsewhere source texts plus all relevant candidate texts",
        "word_vectoriser": WORD_OPTIONS, "character_vectoriser": CHAR_OPTIONS,
        "fitted_vocabulary_sizes": comp.vocabulary_sizes,
        "title_similarity": "2*longest_common_subsequence_length/(combined_normalised_title_length); missing titles supply zero evidence",
        "baseline_weights_word_character_title_compatibility": list(BASELINE_WEIGHTS),
        "compatibility": "Indicator of at least one shared stored IFEP identifier",
        "primary_eligibility": "Shared IFEP required before ranking; source identifier excluded",
        "documentary_unresolved_definition": "No resolvable record-level documentary destination at any inspected stage, including earlier SKB and original-inventory associations; fixed independently of retrieval",
        "alternative_documentary_subset": "The supplied no_resolved_relevant_destination flag identifies records without a resolved relevant PFEP or stage-qualified SKB destination; it is preserved separately",
        "known_relations_removed_from_candidate_pool": False,
        "tie_rule": "Descending score, then ascending PFEP identifier",
        "primary_exploratory_threshold": PRIMARY_THRESHOLD, "threshold_grid": list(THRESHOLDS),
        "models": MODEL_DESCRIPTIONS,
        "title_ablation_score_range_under_shared_IFEP": [0.15, 0.40],
        "title_ablation_primary_threshold_equivalent_title_similarity": (PRIMARY_THRESHOLD - 0.15) / 0.25,
        "fallback_fit_policy": "Vectorisers and candidate vectors remain fixed; only genuinely empty source-text queries are transformed from their titles",
        "fallback_adds_new_source_information": False,
        "fallback_interpretation": "The existing title is reused in text similarity components; missing descriptive content is not imputed",
        "benchmark_primary_scope": "Source-verified, unambiguous directional treatment/replacement/lumping endpoints identified in the original source inventory and available in the relevant candidate pool",
        "benchmark_broader_scope": "Other source-verified directional references, including contextual links, reported separately",
        "benchmark_query_reference_masking": "None: the internal check retrieves references present in the source fields; it is not held-out prediction of undocumented coverage",
        "benchmark_denominator": "Every included source remains a case even when none of its source endpoints passes the taxonomy gate",
        "hit_at_k_definition": "Fraction of source cases with at least one source-specified endpoint among the first k candidates",
        "independent_domain_validation": False,
        "provenance_limit": "Original-inventory references do not establish SKB adoption, exhaustive physical coverage or scenario adequacy",
        "threshold_interpretation": "An exploratory score rule, not a calibrated probability or a documentary state",
    }


def run(data, decision_path=None, relation_path=None, output=None, metadata_only=False):
    data = Path(data)
    output = Path(output) if output is not None else data
    output.mkdir(parents=True, exist_ok=True)
    _, source, relevant = load_population(data)
    comp = build_components(source, relevant)
    decisions, relations = (None, None)
    if not metadata_only:
        decisions, relations = load_documentary_inputs(decision_path or data / "coverage_evidence_200.csv",
                                                       relation_path or data / "provenance_relations.csv",
                                                       source.pfep_id.tolist())
    availability, missingness = text_availability(comp, decisions)
    availability.to_csv(output / "retrieval_source_text_availability.csv", index=False)
    missingness.to_csv(output / "retrieval_field_missingness.csv", index=False)
    (output / "retrieval_specification.json").write_text(json.dumps(specifications(comp), indent=2, ensure_ascii=False) + "\n")
    if metadata_only:
        summary = {"covered_elsewhere_sources_n": len(source), "source_text_empty_n": int(comp.source_text_empty.sum()),
                   "source_text_empty_by_inventory": availability.groupby("project_letter").source_text_empty.sum().astype(int).to_dict()}
        print(json.dumps(summary, indent=2))
        return summary
    models = comp.model_scores()
    results, rankings, orders = search_results(comp, decisions, models)
    thresholds = threshold_sensitivity(results)
    benchmark_cases, benchmark_summary, benchmark_evidence = benchmark_results(comp, relations, models, orders)
    comparison = model_comparison(results)
    weights = weight_sensitivity(comp, decisions, relations)
    for name, frame in {
        "retrieval_search_outcomes.csv": results,
        "retrieval_candidate_rankings.csv": rankings,
        "retrieval_threshold_sensitivity.csv": thresholds,
        "retrieval_benchmark_cases.csv": benchmark_cases,
        "retrieval_benchmark_summary.csv": benchmark_summary,
        "retrieval_benchmark_source_evidence.csv": benchmark_evidence,
        "retrieval_model_comparison.csv": comparison,
        "retrieval_weight_sensitivity.csv": weights,
    }.items():
        frame.to_csv(output / name, index=False)
    primary = results[results.documentary_unresolved.eq(1) & results.model.eq(PRIMARY_MODEL)
                      & results.eligibility_rule.eq(PRIMARY_GATE)]
    primary_benchmark = benchmark_summary[benchmark_summary.benchmark_scope.eq("strict_source_endpoints")
                         & benchmark_summary.model.eq(PRIMARY_MODEL)
                         & benchmark_summary.eligibility_rule.eq(PRIMARY_GATE)]
    by_inventory = {}
    for inventory, frame in primary.groupby("project_letter"):
        by_inventory[inventory] = {"documentary_unresolved_n": len(frame),
                                  "source_text_empty_n": int(frame.source_text_empty.sum()),
                                  **{status + "_n": int(frame.search_outcome.eq(status).sum()) for status in OUTCOMES}}
    summary = {"covered_elsewhere_sources_n": len(source), "relevant_candidate_pool_n": len(relevant),
               "documentary_unresolved_n": int(decisions.documentary_unresolved.sum()),
               "source_text_empty_n": int(comp.source_text_empty.sum()),
               "source_text_empty_by_inventory": availability.groupby("project_letter").source_text_empty.sum().astype(int).to_dict(),
               "documentary_unresolved_empty_source_text_n": int(primary.source_text_empty.sum()),
               "primary_search_outcomes": {status + "_n": int(primary.search_outcome.eq(status).sum()) for status in OUTCOMES},
               "primary_search_outcomes_by_inventory": by_inventory,
               "baseline_equals_title_ablation_for_empty_source_text": bool(np.array_equal(models[PRIMARY_MODEL][comp.source_text_empty], models["title_only_ablation"][comp.source_text_empty])),
               "fallback_leaves_nonempty_queries_unchanged": bool(np.array_equal(models[PRIMARY_MODEL][~comp.source_text_empty], models["missing_text_title_fallback"][~comp.source_text_empty])),
               "primary_strict_benchmark": primary_benchmark.to_dict(orient="records")[0],
               "independent_domain_validation": False,
               "documentary_inputs_modified": False}
    if "no_resolved_relevant_destination" in results:
        alternative = results[results.no_resolved_relevant_destination.eq(1)
                              & results.model.eq(PRIMARY_MODEL)
                              & results.eligibility_rule.eq(PRIMARY_GATE)]
        summary["no_resolved_relevant_destination_n"] = len(alternative)
        summary["alternative_subset_primary_search_outcomes"] = {
            status + "_n": int(alternative.search_outcome.eq(status).sum()) for status in OUTCOMES}
    summary = json_safe(summary)
    (output / "retrieval_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--relations", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args(argv)
    run(args.data_dir, args.decisions, args.relations, args.output_dir, args.metadata_only)


if __name__ == "__main__":
    main()
