#!/usr/bin/env python3
"""Census of non-Project N records and threshold-free retrieval checks.

Inputs are the archived, source-qualified tables in the replication package.
The script creates derived tables in --output and never modifies its inputs.
No weights, cutoffs, or model choices are selected against the endpoint set.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

import numpy as np
import pandas as pd
import scipy
from scipy.stats import chi2_contingency
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


CLASSES = [
    "SR-Site-stage SKB association", "Earlier-stage SKB association",
    "Original-inventory reference", "SKB rationale without identifiable destination",
    "No identifiable documentary destination",
]
SOURCE_FIELD_KEYS = {
    "FEP DESCRIPTION": "pfep_description", "COMMENTS": "pfep_comments",
    "COMMENTS NEEDS DISCUSSION": "comments_needs_discussion",
    "ASSESSMENT BASIS COMMENT": "assessment_basis_comment",
}
DOMAIN_PREFIXES = {
    "0": "Assessment basis, models and data",
    "1.1": "Repository implementation and quality control",
    "1.2": "Geological events and processes",
    "1.3": "Climatic and ecological change",
    "1.4": "Human actions",
    "1.5": "Other external factors",
    "2.1": "Wastes and engineered barriers",
    "2.2": "Geosphere",
    "2.3": "Surface environment",
    "3.1": "Contaminant characteristics",
    "3.2": "Contaminant release and migration",
    "3.3": "Exposure factors",
}
MODEL_WEIGHTS = {
    "archived_weighted_score": [0.35, 0.25, 0.25, 0.15],
    "weighted_content_only": [0.35 / 0.85, 0.25 / 0.85, 0.25 / 0.85, 0.0],
    "equal_content_weights": [1 / 3, 1 / 3, 1 / 3, 0.0],
    "word_tfidf_only": [1.0, 0.0, 0.0, 0.0],
    "character_tfidf_only": [0.0, 1.0, 0.0, 0.0],
    "title_similarity_only": [0.0, 0.0, 1.0, 0.0],
}
DERIVED_FILES = [
    "non_project_n_census_55.csv", "non_project_n_unresolved_records_19.csv",
    "non_project_n_inventory_summary.csv", "non_project_n_domain_summary.csv",
    "non_project_n_reason_by_class.csv", "non_project_n_summary.json",
    "inventory_relevance_association.csv", "inventory_relevance_chi2_cells.csv",
    "retrieval_identifier_mask_audit.csv", "retrieval_benchmark_query_texts.csv",
    "retrieval_benchmark_verified_occurrences_44.csv", "retrieval_benchmark_unique_pairs_42.csv",
    "retrieval_rank_comparison_cases.csv", "retrieval_rank_comparison_pairs.csv",
    "retrieval_rank_comparison_top20.csv", "retrieval_rank_comparison_summary.csv",
    "retrieval_main_table_seven_rows.csv", "retrieval_rank_comparison_specification.json",
    "cohort_retrieval_input_hashes.json",
]


def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def truth(value):
    return str(value).lower() in {"1", "true"}


def dumps(value):
    return json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def identifiers(value):
    return {v.strip() for v in value.split(";") if v.strip()}


def domains(numbers):
    found = set()
    for number in re.findall(r"\d+(?:\.\d+)+", numbers):
        prefix = "0" if number.startswith("0.") else ".".join(number.split(".")[:2])
        if prefix not in DOMAIN_PREFIXES:
            raise ValueError(f"Unspecified IFEP domain prefix: {prefix}")
        found.add(DOMAIN_PREFIXES[prefix])
    return sorted(found)


def association_statistics(population):
    rows, cells = [], []
    for scope, selected in [
        ("All inventories", population),
        ("Project N excluded", population[population.project_letter.ne("N")]),
    ]:
        table = pd.crosstab(selected.project_letter, selected.relevance)
        observed = table.to_numpy()
        n = int(observed.sum())
        r, k = observed.shape
        chi2, _, dof, expected = chi2_contingency(observed, correction=False)
        ordinary = float(np.sqrt(chi2 / n / min(r - 1, k - 1)))
        corrected_phi2 = max(0.0, chi2 / n - (r - 1) * (k - 1) / (n - 1))
        corrected_dimensions = min(r - (r - 1) ** 2 / (n - 1) - 1,
                                   k - (k - 1) ** 2 / (n - 1) - 1)
        bias_corrected = float(np.sqrt(corrected_phi2 / corrected_dimensions))
        contributions = (observed - expected) ** 2 / expected
        rows.append({"scope": scope, "records_n": n, "inventories_n": r,
                     "relevance_categories_n": k, "pearson_chi2": float(chi2),
                     "degrees_of_freedom": int(dof), "ordinary_cramers_v": ordinary,
                     "bias_corrected_cramers_v": bias_corrected})
        for i, inventory in enumerate(table.index):
            for j, status in enumerate(table.columns):
                cells.append({"scope": scope, "project_letter": inventory,
                              "relevance": status, "observed_n": int(observed[i, j]),
                              "expected_n": float(expected[i, j]),
                              "chi2_contribution": float(contributions[i, j]),
                              "share_total_chi2": float(contributions[i, j] / chi2)})
    return pd.DataFrame(rows), pd.DataFrame(cells)


def cohort_census(data, output, population, sources):
    coverage = read_csv(data / "coverage_evidence_200.csv")
    relations = read_csv(data / "provenance_relations.csv")
    profiles = read_csv(data / "source_inventory_profiles_10.csv").set_index("project_letter")
    catalogue = read_csv(data / "srsite_catalogue_407.csv").set_index("sr_id")
    retrieval = read_csv(data / "retrieval_search_outcomes.csv")
    retrieval = retrieval[retrieval.model.eq("baseline_text_fields") &
                          retrieval.eligibility_rule.eq("shared_IFEP_required")].set_index("source_pfep_id")
    pop = population.set_index("pfep_id")
    original = sources.set_index("pfep_id")
    cohort = coverage[coverage.project_letter.ne("N")].copy()
    if len(cohort) != 55 or not cohort.pfep_id.is_unique:
        raise ValueError("Non-Project N cohort must identify 55 unique coverage records")
    rows = []
    for record in cohort.to_dict("records"):
        identifier = record["pfep_id"]
        source = original.loc[identifier]
        mapping = json.loads(record["source_fields_json"])["NEA mapping_SRSite.KSE"]
        target_ids = identifiers(record["resolved_destination_ids"])
        target_components = sorted({catalogue.loc[target, "system_component"]
                                    for target in target_ids if target in catalogue.index
                                    and "system_component" in catalogue.columns
                                    and catalogue.loc[target, "system_component"]})
        related = relations[relations.source_pfep_id.eq(identifier)]
        numeric_fields = ["documentary_unresolved", "no_resolved_relevant_destination",
                          "n_unique_resolved_destinations", "current_association_present",
                          "historical_association_present", "original_inventory_reference_present",
                          "reference_resolution_issue_present", "status_conflict_present",
                          "skb_explanatory_rationale_present", "skb_discussion_targeted_assertion_present",
                          "skb_discussion_scope_rationale_present",
                          "n_current_association_destinations", "n_historical_association_destinations",
                          "n_original_inventory_reference_destinations", "n_benchmark_destinations"]
        row = {"pfep_id": identifier, "project_letter": record["project_letter"],
               "project_reference": pop.loc[identifier, "project_reference"],
               "project_title": pop.loc[identifier, "project_title"],
               "source_scope_type": profiles.loc[record["project_letter"], "project_scope_type"],
               "pfep_title": record["pfep_name"],
               "formal_coverage_reason": record["reason"],
               "formal_heading_only": int(source.heading_only_flag),
               "formal_too_general": int(source.too_general_flag),
               "documentary_class": record["documentary_class"]}
        row.update({name: int(record[name]) for name in numeric_fields})
        row.update({"stored_ifep_identifiers": pop.loc[identifier, "international_fep_numbers_all"],
                    "stored_ifep_names": pop.loc[identifier, "international_fep_names_all"],
                    "stored_ifep_domains": "; ".join(domains(pop.loc[identifier, "international_fep_numbers_all"])),
                    "selected_system_component": mapping.get("SYSTEM COMPONENT", ""),
                    "catalogue_components_for_resolved_identifiers": "; ".join(target_components),
                    "selected_process": mapping.get("SELECTED PROCESS", ""),
                    "selected_variable": mapping.get("SELECTED VARIABLE", ""),
                    "resolved_destination_identifiers": record["resolved_destination_ids"],
                    "relation_identifiers": "; ".join(related.relation_id),
                    "relation_origin_layers": "; ".join(sorted(set(related.origin_layer))),
                    "relation_semantics": "; ".join(sorted(set(related.relation_semantics))),
                    "source_description": record["imported_description_raw"],
                    "source_comments": record["imported_comments_raw"],
                    "skb_discussion": record["skb_discussion_raw"],
                    "skb_assessment_basis": record["skb_assessment_basis_raw"],
                    "record_interpretation": record["interpretation_rationale"],
                    "source_query_empty": int(retrieval.loc[identifier, "source_text_empty"]),
                    "retrieval_eligible_candidates_n": int(retrieval.loc[identifier, "eligible_candidate_n"]),
                    "retrieval_first_candidate_id": retrieval.loc[identifier, "top_target_id"],
                    "retrieval_first_candidate_score": retrieval.loc[identifier, "top_score"],
                    "retrieval_lead_flag": retrieval.loc[identifier, "search_outcome"],
                    "mapping_release": record["mapping_database_version"],
                    "mapping_revision_date": record["mapping_revision_date"]})
        rows.append(row)
    census = pd.DataFrame(rows)
    census.to_csv(output / "non_project_n_census_55.csv", index=False)
    unresolved = census[census.documentary_unresolved.eq(1)].copy()
    unresolved["proposed_record_check"] = unresolved.documentary_class.map({
        "No identifiable documentary destination": "Identify the represented child set for an organizational heading, or record applicable receiving processes and scope exclusions for a technical aggregation.",
        "SKB rationale without identifiable destination": "Retain the general or methodological rationale and identify the receiving assessment task or process when the decision is reused.",
        "Earlier-stage SKB association": "Qualify the historical matrix element by stage and component; record its successor and the scope carried into the current assessment.",
    })
    unresolved[["pfep_id", "project_letter", "pfep_title", "formal_coverage_reason",
                "documentary_class", "stored_ifep_names", "skb_discussion", "skb_assessment_basis",
                "record_interpretation", "proposed_record_check"]].to_csv(
                    output / "non_project_n_unresolved_records_19.csv", index=False)
    summaries = []
    for letter, profile in profiles.iterrows():
        group = census[census.project_letter.eq(letter)]
        if letter == "N":
            continue
        status = population[population.project_letter.eq(letter)].relevance
        summary = {"project_letter": letter, "project_reference": profile.project_reference,
                   "source_scope_type": profile.project_scope_type,
                   "source_population_n": len(status),
                   "relevant_n": int(status.str.lower().eq("relevant").sum()),
                   "not_relevant_n": int(status.str.lower().eq("not relevant").sum()),
                   "coverage_records_n": len(group),
                   "formal_heading_only_n": int(group.formal_heading_only.sum()),
                   "formal_too_general_n": int(group.formal_too_general.sum()),
                   "resolvable_association_sources_n": int(group.documentary_unresolved.eq(0).sum()),
                   "unresolved_association_sources_n": int(group.documentary_unresolved.eq(1).sum()),
                   "no_resolved_relevant_destination_n": int(group.no_resolved_relevant_destination.sum())}
        for cls in CLASSES:
            summary[cls] = int(group.documentary_class.eq(cls).sum())
        summaries.append(summary)
    by_inventory = pd.DataFrame(summaries)
    by_inventory.to_csv(output / "non_project_n_inventory_summary.csv", index=False)
    domain_rows = []
    for domain in DOMAIN_PREFIXES.values():
        group = census[census.stored_ifep_domains.map(lambda value: domain in value.split("; "))]
        if len(group):
            domain_rows.append({"domain_from_stored_ifep": domain, "records_n": len(group),
                                "formal_heading_only_n": int(group.formal_heading_only.sum()),
                                "resolvable_association_n": int(group.documentary_unresolved.eq(0).sum()),
                                "unresolved_association_n": int(group.documentary_unresolved.eq(1).sum()),
                                "record_ids": "; ".join(group.pfep_id)})
    pd.DataFrame(domain_rows).to_csv(output / "non_project_n_domain_summary.csv", index=False)
    by_reason = census.groupby(["formal_coverage_reason", "documentary_class"]).agg(
        sources_n=("pfep_id", "size"), unresolved_n=("documentary_unresolved", "sum")
    ).reset_index()
    by_reason.to_csv(output / "non_project_n_reason_by_class.csv", index=False)
    stats, cells = association_statistics(population)
    stats.to_csv(output / "inventory_relevance_association.csv", index=False)
    cells.to_csv(output / "inventory_relevance_chi2_cells.csv", index=False)
    scalar = {"cohort_n": len(census), "formal_heading_only_n": int(census.formal_heading_only.sum()),
              "formal_too_general_n": int(census.formal_too_general.sum()),
              "resolvable_association_n": int(census.documentary_unresolved.eq(0).sum()),
              "unresolved_association_n": int(census.documentary_unresolved.sum()),
              "unresolved_fraction": float(census.documentary_unresolved.mean()),
              "no_resolved_relevant_destination_n": int(census.no_resolved_relevant_destination.sum()),
              "nonempty_query_n": int(census.source_query_empty.eq(0).sum()),
              "documentary_class_counts": census.documentary_class.value_counts().to_dict(),
              "inventory_counts": census.project_letter.value_counts().sort_index().to_dict(),
              "no_destination_source_ids": census.loc[census.documentary_class.eq(CLASSES[-1]), "pfep_id"].tolist(),
              "unresolved_source_ids": census.loc[census.documentary_unresolved.eq(1), "pfep_id"].tolist(),
              "multiple_resolved_destinations_n": int(census.n_unique_resolved_destinations.gt(1).sum()),
              "single_resolved_destination_n": int(census.n_unique_resolved_destinations.eq(1).sum()),
              "ifep_domain_counts_are_overlapping": True,
              "no_ifep_domain_n": int(census.stored_ifep_domains.eq("").sum()),
              "association_statistics": stats.to_dict("records"),
              "project_n_share_full_chi2": float(cells.loc[
                  cells.scope.eq("All inventories") & cells.project_letter.eq("N"), "share_total_chi2"].sum())}
    (output / "non_project_n_summary.json").write_text(dumps(scalar))
    return scalar


def mask_audited_identifiers(sources, relations):
    """Remove numeric identifier tokens only inside audited evidence spans.

    Target titles, semantic descriptions, source titles and candidates are
    unchanged. A numeric string outside a verified PFEP-reference span is never
    removed, avoiding accidental deletion of physical quantities and dates.
    Overlapping relation spans are combined before edits are applied.
    """
    masked = sources.copy()
    locations = {}
    audit_rows = []
    numeric = re.compile(r"(?:[A-Z]\s+)?\d+(?:\.\d+)*\Z")
    selected = relations[relations.reference_verified.map(truth) &
                         relations.target_type.eq("PFEP") &
                         relations.source_field.isin(SOURCE_FIELD_KEYS)]
    index = {identifier: i for i, identifier in enumerate(sources.pfep_id)}
    for relation in selected.to_dict("records"):
        literal = clean(relation["target_literal"])
        if not numeric.fullmatch(literal):
            continue
        field = SOURCE_FIELD_KEYS[relation["source_field"]]
        identifier = relation["source_pfep_id"]
        text = clean(sources.iloc[index[identifier]][field])
        span = clean(relation["evidence_span"])
        if not span:
            raise ValueError("A numeric reference has an empty evidence span")
        span_starts = [match.start() for match in re.finditer(re.escape(span), text)]
        if not span_starts:
            raise ValueError(f"Evidence span absent from source text: {relation['relation_id']}")
        # The terminal dot in prose punctuation is allowed. A following .digit
        # would be a longer identifier and is therefore excluded.
        pattern = re.compile(r"(?<![A-Za-z0-9.])" + re.escape(literal) + r"(?![A-Za-z0-9]|\.\d)")
        within = list(pattern.finditer(span))
        if not within:
            raise ValueError(f"Numeric literal absent from evidence span: {relation['relation_id']}")
        for span_start in span_starts:
            for match in within:
                start, end = span_start + match.start(), span_start + match.end()
                key = (identifier, field, start, end)
                locations[key] = literal
                audit_rows.append({"source_pfep_id": identifier, "source_field": field,
                                   "relation_id": relation["relation_id"],
                                   "target_id": relation["target_id"],
                                   "target_literal_removed": literal,
                                   "cleaned_field_start": start, "cleaned_field_end": end,
                                   "evidence_span": span})
    for identifier, index_value in index.items():
        for field in SOURCE_FIELD_KEYS.values():
            text = clean(sources.iloc[index_value][field])
            intervals = sorted([(start, end) for (source_id, field_name, start, end) in locations
                                if source_id == identifier and field_name == field], reverse=True)
            for start, end in intervals:
                text = text[:start] + " " + text[end:]
            masked.at[index_value, field] = clean(text)
    audit = pd.DataFrame(audit_rows).drop_duplicates()
    return masked, audit, locations


def retrieval_checks(data, output, sources, relevant, semantic):
    relations = read_csv(data / "provenance_relations.csv")
    gold_occurrences = relations[relations.benchmark_eligible.map(truth)].copy()
    assert gold_occurrences.reference_verified.map(truth).all()
    assert gold_occurrences.direction_valid.map(truth).all()
    gold = gold_occurrences[["source_pfep_id", "target_id"]].drop_duplicates()
    assert len(gold) == 42 and len(gold_occurrences) == 44
    source_ids = sorted(set(gold.source_pfep_id))
    assert len(source_ids) == 18
    relevant_ids = relevant.pfep_id.tolist()
    candidate_index = {identifier: i for i, identifier in enumerate(relevant_ids)}
    source_index = {identifier: i for i, identifier in enumerate(sources.pfep_id)}
    assert set(gold.target_id).issubset(candidate_index)
    comp = semantic.build_components(sources, relevant)
    masked, mask_audit, mask_locations = mask_audited_identifiers(sources, relations)
    mask_audit.to_csv(output / "retrieval_identifier_mask_audit.csv", index=False)
    source_text = comp.source_text.tolist()
    candidate_text = comp.candidate_text.tolist()
    masked_text = masked[list(semantic.SOURCE_FIELDS)].apply(
        lambda row: clean(" ".join(clean(value) for value in row)), axis=1).tolist()
    corpus = source_text + candidate_text
    matrix_pairs = []
    vocab_sizes = []
    for options, expected in [(semantic.WORD_OPTIONS, comp.word),
                              (semantic.CHAR_OPTIONS, comp.character)]:
        vectorizer = TfidfVectorizer(**options)
        matrix = vectorizer.fit_transform(corpus)
        target_matrix = matrix[len(sources):]
        original_scores = cosine_similarity(matrix[:len(sources)], target_matrix)
        assert np.allclose(original_scores, expected)
        masked_scores = cosine_similarity(vectorizer.transform(masked_text), target_matrix)
        matrix_pairs.append((original_scores, masked_scores))
        vocab_sizes.append(len(vectorizer.vocabulary_))
    query_rows = []
    for identifier in source_ids:
        i = source_index[identifier]
        count = sum(key[0] == identifier for key in mask_locations)
        query_rows.append({"source_pfep_id": identifier, "source_title": sources.iloc[i].pfep_name,
                           "unmasked_query": source_text[i], "identifier_masked_query": masked_text[i],
                           "numeric_reference_tokens_removed_n": count,
                           "source_title_unchanged": 1, "semantic_target_names_retained": 1})
    queries = pd.DataFrame(query_rows)
    queries.to_csv(output / "retrieval_benchmark_query_texts.csv", index=False)
    gold_occurrences.to_csv(output / "retrieval_benchmark_verified_occurrences_44.csv", index=False)
    gold.to_csv(output / "retrieval_benchmark_unique_pairs_42.csv", index=False)
    case_rows, pair_rows, top_rows = [], [], []
    for query_variant, q_index in [("unmasked", 0), ("audited_numeric_identifiers_masked", 1)]:
        W, C = matrix_pairs[0][q_index], matrix_pairs[1][q_index]
        for model, weights in MODEL_WEIGHTS.items():
            scores = semantic.score(W, C, comp.title, comp.shared_ifep, weights=weights)
            for gate, gate_required in [("shared_IFEP_required", True),
                                        ("no_IFEP_eligibility_filter", False)]:
                for identifier in source_ids:
                    i = source_index[identifier]
                    endpoints = sorted(set(gold.loc[gold.source_pfep_id.eq(identifier), "target_id"]))
                    order = semantic.rank_candidates(scores[i], comp.shared_ifep[i], relevant_ids,
                                                     excluded={identifier}, require_shared=gate_required)
                    positions = {relevant_ids[j]: rank for rank, j in enumerate(order, 1)}
                    endpoint_ranks = {endpoint: positions[endpoint] for endpoint in endpoints
                                      if endpoint in positions}
                    best = min(endpoint_ranks.values()) if endpoint_ranks else None
                    row = {"query_variant": query_variant, "model": model, "eligibility_rule": gate,
                           "source_pfep_id": identifier, "source_title": sources.iloc[i].pfep_name,
                           "candidate_population_n": len(relevant), "eligible_candidates_n": len(order),
                           "verified_endpoint_n": len(endpoints), "eligible_verified_endpoint_n": len(endpoint_ranks),
                           "verified_endpoint_ids": "; ".join(endpoints),
                           "eligible_endpoint_ranks_json": json.dumps(endpoint_ranks, sort_keys=True),
                           "best_endpoint_rank": best,
                           "reciprocal_rank": 1 / best if best else 0.0,
                           "first_candidate_id": relevant_ids[order[0]] if order else "",
                           "first_candidate_score": float(scores[i, order[0]]) if order else None,
                           "identifiers_removed_from_query_n": int(queries.set_index("source_pfep_id").loc[identifier, "numeric_reference_tokens_removed_n"])
                           if q_index else 0}
                    for k in [1, 5, 10, 20]:
                        row[f"hit_at_{k}"] = int(best is not None and best <= k)
                        row[f"verified_endpoints_at_{k}_n"] = sum(rank <= k for rank in endpoint_ranks.values())
                        row[f"verified_endpoint_recall_at_{k}"] = row[f"verified_endpoints_at_{k}_n"] / len(endpoints)
                    case_rows.append(row)
                    for endpoint in endpoints:
                        j = candidate_index[endpoint]
                        pair_rows.append({"query_variant": query_variant, "model": model,
                                          "eligibility_rule": gate, "source_pfep_id": identifier,
                                          "verified_endpoint_id": endpoint,
                                          "endpoint_shares_ifep": int(comp.shared_ifep[i, j] > 0),
                                          "endpoint_eligible": int(endpoint in positions),
                                          "endpoint_rank": positions.get(endpoint),
                                          "endpoint_score": float(scores[i, j])})
                    for rank, j in enumerate(order[:20], 1):
                        top_rows.append({"query_variant": query_variant, "model": model,
                                         "eligibility_rule": gate, "source_pfep_id": identifier,
                                         "rank": rank, "candidate_id": relevant_ids[j],
                                         "candidate_title": relevant.iloc[j].pfep_name,
                                         "is_verified_endpoint": int(relevant_ids[j] in endpoints),
                                         "word_cosine": float(W[i, j]), "character_cosine": float(C[i, j]),
                                         "title_indel_similarity": float(comp.title[i, j]),
                                         "shared_ifep_count": int(comp.shared_ifep[i, j]),
                                         "score": float(scores[i, j])})
    cases = pd.DataFrame(case_rows)
    pairs = pd.DataFrame(pair_rows)
    summary_rows = []
    for (query, model, gate), group in cases.groupby(["query_variant", "model", "eligibility_rule"], sort=False):
        summary = {"query_variant": query, "model": model, "eligibility_rule": gate,
                   "benchmark_sources_n": len(group),
                   "sources_with_eligible_endpoint_n": int(group.eligible_verified_endpoint_n.gt(0).sum()),
                   "total_verified_endpoints_n": int(group.verified_endpoint_n.sum()),
                   "eligible_verified_endpoints_n": int(group.eligible_verified_endpoint_n.sum()),
                   "mean_reciprocal_rank": float(group.reciprocal_rank.mean())}
        for k in [1, 5, 10, 20]:
            summary[f"hit_at_{k}_n"] = int(group[f"hit_at_{k}"].sum())
            summary[f"hit_at_{k}_fraction"] = float(group[f"hit_at_{k}"].mean())
            summary[f"verified_endpoint_recall_at_{k}_macro"] = float(group[f"verified_endpoint_recall_at_{k}"].mean())
            summary[f"verified_endpoint_recall_at_{k}_micro"] = float(group[f"verified_endpoints_at_{k}_n"].sum() / group.verified_endpoint_n.sum())
        summary_rows.append(summary)
    summary = pd.DataFrame(summary_rows)
    cases.to_csv(output / "retrieval_rank_comparison_cases.csv", index=False)
    pairs.to_csv(output / "retrieval_rank_comparison_pairs.csv", index=False)
    pd.DataFrame(top_rows).to_csv(output / "retrieval_rank_comparison_top20.csv", index=False)
    summary.to_csv(output / "retrieval_rank_comparison_summary.csv", index=False)
    table_choices = [
        ("Weighted score", "unmasked", "archived_weighted_score", "shared_IFEP_required"),
        ("Equal content weights", "unmasked", "equal_content_weights", "shared_IFEP_required"),
        ("Word TF-IDF", "unmasked", "word_tfidf_only", "shared_IFEP_required"),
        ("Character TF-IDF", "unmasked", "character_tfidf_only", "shared_IFEP_required"),
        ("Title similarity", "unmasked", "title_similarity_only", "shared_IFEP_required"),
        ("Weighted score, numeric references masked", "audited_numeric_identifiers_masked",
         "archived_weighted_score", "shared_IFEP_required"),
        ("Weighted score, no IFEP gate", "unmasked", "archived_weighted_score", "no_IFEP_eligibility_filter"),
    ]
    table_rows = []
    for label, query, model, gate in table_choices:
        row = summary[summary.query_variant.eq(query) & summary.model.eq(model) &
                      summary.eligibility_rule.eq(gate)].iloc[0].to_dict()
        table_rows.append({"comparison_label": label, **row})
    pd.DataFrame(table_rows).to_csv(output / "retrieval_main_table_seven_rows.csv", index=False)
    # The new implementation must exactly reproduce every historical unmasked
    # strict benchmark rank before its sensitivity outputs can be interpreted.
    archived = read_csv(data / "retrieval_benchmark_cases.csv")
    archived = archived[archived.benchmark_scope.eq("strict_source_endpoints") &
                        archived.model.eq("baseline_text_fields")]
    reproduced = cases[cases.query_variant.eq("unmasked") &
                       cases.model.eq("archived_weighted_score")]
    for record in archived.to_dict("records"):
        same = reproduced[reproduced.source_pfep_id.eq(record["source_pfep_id"]) &
                          reproduced.eligibility_rule.eq(record["eligibility_rule"])].iloc[0]
        expected_rank = float(record["best_source_endpoint_rank"]) if record["best_source_endpoint_rank"] else np.nan
        assert (pd.isna(expected_rank) and pd.isna(same.best_endpoint_rank)) or expected_rank == same.best_endpoint_rank
        assert json.loads(record["source_endpoint_ranks"]) == json.loads(same.eligible_endpoint_ranks_json)
    config = {
        "candidate_population": "All 1301 PFEPs classified Relevant in the archived population",
        "source_population_for_vectorizer_fit": "All 200 coverage-elsewhere records, unchanged",
        "benchmark_sources_n": 18, "unique_source_endpoint_pairs_n": 42,
        "source_verified_provenance_occurrences_n": 44,
        "source_fields": list(semantic.SOURCE_FIELDS), "candidate_fields": list(semantic.CANDIDATE_FIELDS),
        "title_field": "pfep_name", "title_metric": "2*LCS/(combined normalized title length)",
        "word_options": semantic.WORD_OPTIONS, "character_options": semantic.CHAR_OPTIONS,
        "vectorizer_fit": "One unmasked joint corpus of 200 source texts plus 1301 candidate texts for each vectorizer; masked queries transform in the same fixed vocabulary and IDF weights",
        "vocabulary_sizes": {"word": vocab_sizes[0], "character": vocab_sizes[1]},
        "score_weights_order": ["word_cosine", "character_cosine", "title_indel_similarity", "shared_ifep_indicator"],
        "models": MODEL_WEIGHTS,
        "eligibility_variants": ["shared_IFEP_required", "no_IFEP_eligibility_filter"],
        "tie_break": "Ascending PFEP identifier after descending score",
        "masking": "Remove only numeric/full PFEP identifier literals inside source-verified PFEP-reference evidence spans. Replace each token by whitespace. Titles and named semantic references remain. Candidate records, vectorizer fit and IFEP metadata remain fixed.",
        "masked_benchmark_queries_n": int(queries.numeric_reference_tokens_removed_n.gt(0).sum()),
        "numeric_tokens_removed_in_benchmark_n": int(queries.numeric_reference_tokens_removed_n.sum()),
        "numeric_tokens_removed_all_200_n": len(mask_locations),
        "masked_queries_are_not_independent_validation": True,
        "weight_optimization": "None. No objective function or held-out tuning set selected the archived weights or the 0.34 lead flag. No optimization is performed in this comparison.",
        "cutoff_use": "The archived 0.34 threshold labels follow-up leads only; no cutoff is used for the rank comparisons.",
        "benchmark_interpretation": "Recovery of identified imported cross-reference endpoints; neither complete relevance judgments nor validation of documentary adoption, screening adequacy or safety performance.",
        "dense_model_benchmark_performed": False,
        "software": {"python": platform.python_version(), "numpy": np.__version__,
                     "pandas": pd.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
    }
    (output / "retrieval_rank_comparison_specification.json").write_text(dumps(config))
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    data = package / "data"
    sys.path.insert(0, str(package / "code" / "semantic"))
    import traceability_semantics as semantic
    population, sources, relevant = semantic.load_population(data)
    inputs = [data / name for name in ["coverage_evidence_200.csv", "provenance_relations.csv",
              "source_inventory_profiles_10.csv", "pfep_relevance_population_1671.csv",
              "not_relevant_370_normalized.csv", "srsite_catalogue_407.csv",
              "retrieval_search_outcomes.csv", "retrieval_benchmark_cases.csv"]]
    inputs.append(package / "code" / "semantic" / "traceability_semantics.py")
    before = {str(path.relative_to(package)): sha256(path) for path in inputs}
    census = cohort_census(data, output, population, sources)
    config = retrieval_checks(data, output, sources, relevant, semantic)
    after = {str(path.relative_to(package)): sha256(path) for path in inputs}
    assert before == after, "Scientific inputs were unexpectedly modified"
    (output / "cohort_retrieval_input_hashes.json").write_text(dumps(before))
    manifest = []
    for role, paths, anchor in [("input", inputs, package),
                                ("derived", [output / name for name in DERIVED_FILES], output)]:
        for path in paths:
            manifest.append({"role": role, "path_relative_to": "package" if role == "input" else "output",
                             "relative_path": str(path.relative_to(anchor)), "sha256": sha256(path),
                             "bytes": path.stat().st_size,
                             "csv_records_n": len(read_csv(path)) if path.suffix == ".csv" else ""})
    pd.DataFrame(manifest).to_csv(output / "cohort_retrieval_files_manifest.csv", index=False)
    print(dumps({"cohort_n": census["cohort_n"], "unresolved_n": census["unresolved_association_n"],
                 "benchmark_sources_n": config["benchmark_sources_n"],
                 "masked_benchmark_queries_n": config["masked_benchmark_queries_n"],
                 "output": str(output)}))


if __name__ == "__main__":
    main()
