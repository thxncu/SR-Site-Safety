#!/usr/bin/env python3
"""Check scientific invariants of cohort and retrieval-comparison outputs."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from compute_cohort_and_retrieval_checks import mask_audited_identifiers, read_csv, clean


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data, output = args.package / "data", args.output
    census = read_csv(output / "non_project_n_census_55.csv")
    original = read_csv(data / "coverage_evidence_200.csv")
    expected = original[original.project_letter.ne("N")].set_index("pfep_id")
    assert set(census.pfep_id) == set(expected.index)
    assert census.pfep_id.is_unique and len(census) == 55
    for source in census.to_dict("records"):
        row = expected.loc[source["pfep_id"]]
        for column in ["documentary_class", "documentary_unresolved", "no_resolved_relevant_destination"]:
            assert row[column] == source[column]
        assert row["imported_description_raw"] == source["source_description"]
        assert row["skb_discussion_raw"] == source["skb_discussion"]
        assert row["resolved_destination_ids"] == source["resolved_destination_identifiers"]
    assert census.formal_heading_only.astype(int).sum() == 20
    assert census.formal_too_general.astype(int).sum() == 35
    assert census.source_query_empty.astype(int).sum() == 0
    assert census.documentary_unresolved.astype(int).sum() == 19
    assert census.no_resolved_relevant_destination.astype(int).sum() == 20
    counts = read_csv(output / "non_project_n_inventory_summary.csv").set_index("project_letter")
    assert counts.loc["K", "coverage_records_n"] == "0"
    assert counts.loc["S", "coverage_records_n"] == "1"

    sys.path.insert(0, str(args.package / "code" / "semantic"))
    from traceability_semantics import load_population
    _, source, relevant = load_population(data)
    candidate_before = relevant.to_json()
    masked, _, positions = mask_audited_identifiers(source, read_csv(data / "provenance_relations.csv"))
    assert candidate_before == relevant.to_json()
    assert source.pfep_name.tolist() == masked.pfep_name.tolist()
    assert source.international_fep_numbers_all.tolist() == masked.international_fep_numbers_all.tolist()
    indexed = masked.set_index("pfep_id")
    # A physical quantity in the long WIPP description is not a local FEP ID.
    assert "31 megapascals" in indexed.loc["W 2.072", "pfep_description"]
    assert "53˚ C" in indexed.loc["W 2.072", "pfep_description"]
    # Removing numeric references must preserve their substantive names.
    assert "Colloid Formation (natural & vault generated)" in indexed.loc["I 165", "pfep_description"]
    assert "Degradation of the bentonite" in indexed.loc["J 3.1.12", "pfep_description"]
    # Every change consists exactly of the verified numeric-token deletions.
    source_index = source.set_index("pfep_id")
    for identifier, field in {(key[0], key[1]) for key in positions}:
        text = clean(source_index.loc[identifier, field])
        intervals = sorted([(key[2], key[3]) for key in positions
                            if key[0] == identifier and key[1] == field], reverse=True)
        for start, end in intervals:
            text = text[:start] + " " + text[end:]
        assert clean(text) == indexed.loc[identifier, field]

    cases = pd.read_csv(output / "retrieval_rank_comparison_cases.csv")
    pairs = pd.read_csv(output / "retrieval_rank_comparison_pairs.csv")
    assert len(cases) == 18 * 6 * 2 * 2
    assert len(pairs) == 42 * 6 * 2 * 2
    assert not cases.duplicated(["query_variant", "model", "eligibility_rule", "source_pfep_id"]).any()
    assert not pairs.duplicated(["query_variant", "model", "eligibility_rule", "source_pfep_id", "verified_endpoint_id"]).any()
    for (variant, model, gate), group in cases.groupby(["query_variant", "model", "eligibility_rule"]):
        expected_pairs = pairs[pairs.query_variant.eq(variant) & pairs.model.eq(model) & pairs.eligibility_rule.eq(gate)]
        assert group.eligible_verified_endpoint_n.sum() == expected_pairs.endpoint_eligible.sum()
        assert expected_pairs.endpoint_eligible.sum() == (19 if gate == "shared_IFEP_required" else 42)
        for record in group.to_dict("records"):
            eligible = expected_pairs[expected_pairs.source_pfep_id.eq(record["source_pfep_id"]) & expected_pairs.endpoint_eligible.eq(1)]
            assert len(eligible) == record["eligible_verified_endpoint_n"]
            if len(eligible):
                assert eligible.endpoint_rank.min() == record["best_endpoint_rank"]
            else:
                assert np.isnan(record["best_endpoint_rank"])
    # The compatibility bonus is constant under the gate, so deleting and
    # renormalising that score term must preserve every ranking.
    for variant in cases.query_variant.unique():
        fixed = cases[cases.query_variant.eq(variant) & cases.eligibility_rule.eq("shared_IFEP_required")]
        weighted = fixed[fixed.model.eq("archived_weighted_score")].set_index("source_pfep_id")
        content = fixed[fixed.model.eq("weighted_content_only")].set_index("source_pfep_id")
        assert weighted.eligible_endpoint_ranks_json.to_dict() == content.eligible_endpoint_ranks_json.to_dict()
    title_cases = cases[cases.model.eq("title_similarity_only")]
    before = title_cases[title_cases.query_variant.eq("unmasked")].set_index(["source_pfep_id", "eligibility_rule"])
    after = title_cases[title_cases.query_variant.eq("audited_numeric_identifiers_masked")].set_index(["source_pfep_id", "eligibility_rule"])
    assert before.eligible_endpoint_ranks_json.to_dict() == after.eligible_endpoint_ranks_json.to_dict()
    print(json.dumps({"cohort_identity_and_values": "passed", "scientific_masking_constraints": "passed",
                      "all_source_pair_rank_consistency": "passed", "taxonomy_gate_ceiling": "passed",
                      "score_equivalence_and_title_invariance": "passed"}, indent=2))


if __name__ == "__main__":
    main()
