#!/usr/bin/env python3
"""Reproduce inventory structure and source-page coverage for an evidence register.

Only locators, hashes, search terms, counts and analytical metadata are written.
Copyrighted report text is read locally and is not redistributed in the outputs.
Page retrieval is distinct from purposive selection of analytical passages.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


PATTERNS = {
    "fep": r"\bfep(?:s)?\b",
    "traceability": r"traceab",
    "database": r"databas",
    "document_control": r"document\s+(?:and\s+data\s+)?control",
    "data_control": r"data\s+(?:and\s+document\s+)?control",
    "qualification": r"qualif",
    "quality_assurance": r"quality\s+assurance|\bqa\b",
    "cross_reference": r"cross[-\s]?(?:referenc|document)",
    "mapping": r"\b(?:mapping|mapped)\b",
    "screening": r"\b(?:screening|screened)\b",
}

# Physical PDF positions, counted from one, for the archived editions.
# The two SSM ranges run from Introduction through Recommendations/Conclusions.
# The NEA range runs from High-level findings through the end of Chapter 4.
SOURCES = [
    {
        "source": "SSM 2012:34", "stem": "SSM_2012_34", "first": 11,
        "last": 27, "offset": 8, "context_pages": [26, 27],
        "frame_description": "Printed pp. 3–19, Sections 1–3",
    },
    {
        "source": "SSM 2012:36", "stem": "SSM_2012_36", "first": 11,
        "last": 51, "offset": 8, "context_pages": [47, 48, 49, 50, 51],
        "frame_description": "Printed pp. 3–43, Sections 1–5",
    },
    {
        "source": "OECD/NEA 2012", "stem": "NEA_7084_2012", "first": 11,
        "last": 137, "offset": 2,
        "context_pages": [12, 13, 23, 24, 25, 26, 27, 28, 29],
        "frame_description": "Printed pp. 9–135, High-level findings and Chapters 1–4",
    },
]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def page_range(locator):
    values = [int(value) for value in re.findall(r"\d+", locator)]
    return set(range(values[0], values[-1] + 1))


def normalized(text):
    return re.sub(r"(?<=[A-Za-z])-\s*\n\s*(?=[a-z])", "", text).lower()


def page_frame(package, reports, output):
    register = read_csv(package / "data/external_review_findings_42.csv")
    source_metadata = {row["source"]: row for row in read_csv(package / "data/external_review_sources.csv")}
    all_rows, summary_rows = [], []
    for source in SOURCES:
        report_path = reports / (source["stem"] + ".pdf")
        text_path = reports / (source["stem"] + ".txt")
        source_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
        assert source_sha == source_metadata[source["source"]]["sha256"]
        pages = text_path.read_text(encoding="utf-8").split("\f")
        if not pages[-1].strip():
            pages.pop()
        selected = [row for row in register if row["source"] == source["source"]]
        source_rows = []
        for position, page_text in enumerate(pages, 1):
            in_frame = source["first"] <= position <= source["last"]
            page_normalized = normalized(page_text)
            terms = [name for name, pattern in PATTERNS.items() if re.search(pattern, page_normalized)] if in_frame else []
            finding_ids = [row["finding_id"] for row in selected if position in page_range(row["pdf_page_1based"])]
            row = {
                "source": source["source"],
                "pdf_page_1based": position,
                "printed_page_in_frame": position - source["offset"] if in_frame else "",
                "inside_english_assessment_frame": in_frame,
                "blank_page": not bool(page_text.strip()),
                "keyword_match": bool(terms),
                "matched_term_families": ";".join(terms),
                "mandatory_context_page": position in source["context_pages"],
                "retrieved_page_or_context": bool(terms) or position in source["context_pages"],
                "selected_register_passages": ";".join(finding_ids),
                "page_text_sha256": hashlib.sha256(page_text.encode("utf-8")).hexdigest(),
                "source_pdf_sha256": source_sha,
            }
            source_rows.append(row)
        in_frame_rows = [row for row in source_rows if row["inside_english_assessment_frame"]]
        retrieved = [row for row in in_frame_rows if row["retrieved_page_or_context"]]
        covered = [row for row in source_rows if row["selected_register_passages"]]
        assert all(row["inside_english_assessment_frame"] and row["retrieved_page_or_context"] for row in covered)
        directions = Counter(row["direction"] for row in selected)
        summary_rows.append({
            "source": source["source"],
            "physical_pdf_pages": len(pages),
            "assessment_page_frame": source["frame_description"],
            "frame_pages_including_blank": len(in_frame_rows),
            "frame_blank_pages": sum(row["blank_page"] for row in in_frame_rows),
            "keyword_retrieved_pages": sum(row["keyword_match"] for row in in_frame_rows),
            "additional_context_pages": sum(row["mandatory_context_page"] and not row["keyword_match"] for row in in_frame_rows),
            "retrieved_pages_or_context": len(retrieved),
            "nonblank_frame_pages_without_keyword_match": sum(not row["blank_page"] and not row["keyword_match"] for row in in_frame_rows),
            "pages_locating_selected_passages": len(covered),
            "selected_passages": len(selected),
            "critical_selected_passages": directions["critical"],
            "mixed_selected_passages": directions["mixed"],
            "favorable_selected_passages": directions["favorable"],
            "explicit_summary_recurrences": sum(row["unit_role"] == "summary recurrence" for row in selected),
            "source_url": source_metadata[source["source"]]["source_url"],
            "source_pdf_sha256": source_sha,
        })
        all_rows.extend(source_rows)
    write_csv(output / "external_review_page_frame.csv", all_rows)
    write_csv(output / "external_review_selection_accounting.csv", summary_rows)
    config = {
        "page_frame": SOURCES,
        "normalization": "Lowercase; join alphabetic words split by a hyphen and line break; no stemming beyond listed regular expressions.",
        "term_families": PATTERNS,
        "page_retrieval_role": "Reproducible coverage aid. Nonmatching pages are not coded as substantively irrelevant; candidate pages are not an exhaustive passage denominator.",
        "passage_selection_role": "The 42 analytical statements are purposively selected, with row-level inclusion rationale and source locators. They do not exhaust eligible statements or represent direction prevalence.",
    }
    (output / "external_review_page_retrieval_specification.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    return summary_rows


def inventory_structure(package, output):
    population = read_csv(package / "data/pfep_relevance_population_1671.csv")
    snapshot = json.loads((package / "code/extraction/documentary_source_snapshot.json").read_text())
    n_rows = [row for row in population if row["project_letter"] == "N"]
    identifiers = {row["pfep_id"] for row in n_rows}
    records = snapshot["records"]
    rows = []
    for row in n_rows:
        identifier = row["pfep_id"]
        descendants = sorted(other for other in identifiers if other.startswith(identifier + "."))
        parent_candidates = sorted(other for other in identifiers if identifier.startswith(other + "."))
        record = records.get(identifier, {})
        mapping = record.get("NEA mapping_SRSite.KSE", {})
        rows.append({
            "pfep_id": identifier, "pfep_name": row["pfep_name"],
            "relevance": row["relevance"], "covered_elsewhere_cohort": identifier in records,
            "numeric_parent_id": max(parent_candidates, key=len) if parent_candidates else "",
            "is_numeric_parent": bool(descendants),
            "numeric_descendant_count": len(descendants),
            "numeric_descendant_ids": ";".join(descendants),
            "description_empty": not bool(row["pfep_description"].strip()),
            "comments_empty": not bool(row["pfep_comments"].strip()),
            "recorded_heading_only_coverage_reason": mapping.get("RELEVANCE MOTIVATION", "").strip() == "Heading only, covered by other NEA project FEPs",
            "heading_reason_field": mapping.get("RELEVANCE MOTIVATION", "").strip(),
        })
    heading_other = [{
        "pfep_id": key, "pfep_name": record["PROFEP.KSE"].get("FEP NAME", ""),
        "description_empty": not bool(record["PROFEP.KSE"].get("FEP DESCRIPTION", "").strip()),
        "comments_empty": not bool(record["PROFEP.KSE"].get("COMMENTS", "").strip()),
        "heading_reason_field": record["NEA mapping_SRSite.KSE"].get("RELEVANCE MOTIVATION", "").strip(),
    } for key, record in records.items() if not key.startswith("N ") and "heading only" in record["NEA mapping_SRSite.KSE"].get("RELEVANCE MOTIVATION", "").lower()]
    covered = [row for row in rows if row["covered_elsewhere_cohort"]]
    result = {
        "project_n_population": len(rows),
        "project_n_coverage": len(covered),
        "project_n_coverage_heading_reason": sum(row["recorded_heading_only_coverage_reason"] for row in covered),
        "project_n_coverage_numeric_parents": sum(row["is_numeric_parent"] for row in covered),
        "project_n_coverage_numeric_leaves": sum(not row["is_numeric_parent"] for row in covered),
        "project_n_coverage_description_empty": sum(row["description_empty"] for row in covered),
        "project_n_coverage_comments_empty": sum(row["comments_empty"] for row in covered),
        "project_n_retained_ids": [row["pfep_id"] for row in rows if not row["covered_elsewhere_cohort"]],
        "non_n_coverage_heading_reason": len(heading_other),
        "non_n_coverage_heading_reason_by_inventory": dict(Counter(row["pfep_id"][0] for row in heading_other)),
        "hierarchy_rule": "Identifier X is a numeric parent only when another imported N identifier begins X followed by a period. This measures the archived identifier tree, not semantic subsumption or the sufficiency of coverage.",
    }
    assert result["project_n_population"] == 146
    assert result["project_n_coverage"] == 145
    assert result["project_n_coverage_numeric_parents"] == 15
    assert result["project_n_coverage_numeric_leaves"] == 130
    assert result["project_n_coverage_heading_reason"] == 145
    assert result["non_n_coverage_heading_reason"] == 20
    write_csv(output / "project_n_inventory_structure.csv", rows)
    write_csv(output / "non_n_heading_coverage_records.csv", heading_other)
    (output / "project_n_inventory_structure_summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--reports", type=Path, help="Directory holding the three official PDFs and pdftotext -layout TXT files; omitted for inventory-only reproduction")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    selection = page_frame(args.package, args.reports, args.output) if args.reports else None
    inventory = inventory_structure(args.package, args.output)
    print(json.dumps({"selection": selection, "inventory": inventory}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
