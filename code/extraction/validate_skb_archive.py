#!/usr/bin/env python3
"""Verify normalized source fields and documentary provenance against SKB's archive.

python code/extraction/validate_skb_archive.py /path/to/TR-10-45_FEP_database.zip

Agreement verifies extraction and application of the declared interpretation
rules, not independent adjudication or substantive safety-case coverage.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_covered_elsewhere_audit import parse_filemaker, clean, make_snapshot, build, SOURCE_SNAPSHOT, RULES


def main(archive, data_directory=ROOT / "data"):
    archive = Path(archive)
    data = Path(data_directory)
    manifest = pd.read_csv(ROOT / "source_manifest.csv", dtype=str, keep_default_na=False)
    expected = manifest.loc[manifest.file_name.eq("TR-10-45_FEP_database.zip"), "sha256"].iat[0]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError("The archive checksum differs from source_manifest.csv")
    checks = []

    def result(name, total, matched, scope):
        checks.append({"check": name, "records_compared": total, "records_matched": matched, "scope": scope})
        if total != matched:
            raise ValueError(f"{name}: {matched}/{total} matched")

    required = ["NEA mapping_SRSite", "PROFEP", "HandlingNEAFEPs_SRSite", "SR_Site_FEP_catalogue",
                "Processes_SRSite", "Variables_SRSite", "SR_Can_FEP_catalogue", "SAFEbiomatrix"]
    with tempfile.TemporaryDirectory(prefix="skb_source_", dir=ROOT.parent) as temp:
        temp = Path(temp)
        with zipfile.ZipFile(archive) as zipped:
            for name in required:
                members = [m for m in zipped.namelist() if m.endswith("/" + name + ".KSE") and not m.startswith("__MACOSX/")]
                if len(members) != 1:
                    raise ValueError(f"Expected one source table: {name}")
                (temp / (name + ".KSE")).write_bytes(zipped.read(members[0]))
        mapping = parse_filemaker(temp / "NEA mapping_SRSite.KSE")
        imported = parse_filemaker(temp / "PROFEP.KSE")
        handling = parse_filemaker(temp / "HandlingNEAFEPs_SRSite.KSE")
        catalogue = parse_filemaker(temp / "SR_Site_FEP_catalogue.KSE")
        mapping["id"] = mapping["NEA PROJECT FEP ID"].map(clean)
        imported["id"] = imported["UNIQUE NO."].map(clean)
        pop = pd.read_csv(data / "pfep_relevance_population_1671.csv", dtype=str, keep_default_na=False).assign(id=lambda x: x.pfep_id)
        nr = pd.read_csv(data / "not_relevant_370_normalized.csv", dtype=str, keep_default_na=False).assign(id=lambda x: x.pfep_id)
        result("PFEP identifier population", len(pop), len(set(pop.id) & set(mapping.id)), "Archived SKB SR-Site screening table")
        joined = pop.merge(mapping, on="id", validate="one_to_one")
        described = pop.merge(imported, on="id", validate="one_to_one")
        excluded = nr.merge(mapping, on="id", validate="one_to_one")
        for frame, left, right in [
            (joined, "relevance", "RELEVANCE"), (joined, "revision_date", "REVISION DATE"),
            (described, "pfep_name", "FEP NAME"), (described, "pfep_description", "FEP DESCRIPTION"),
            (described, "pfep_comments", "COMMENTS"),
            (excluded, "relevance_motivation_clean", "RELEVANCE MOTIVATION"),
            (excluded, "comments_needs_discussion", "COMMENTS NEEDS DISCUSSION"),
            (excluded, "assessment_basis_comment", "ASSESSMENT BASIS COMMENT"),
        ]:
            result(left, len(frame), int(frame[left].map(clean).eq(frame[right].map(clean)).sum()), "Whitespace-normalized source field")

        net = pd.read_csv(data / "pfep_srsite_network_edges.csv", dtype=str, keep_default_na=False)
        handling["pfep_id"] = handling["NEA PROJECT FEP ID"].map(clean)
        handling["sr_id"] = handling["SRSITE FEP ID"].map(clean)
        raw_edges = set(zip(handling.pfep_id, handling.sr_id))
        stored_edges = set(zip(net.pfep_id, net.sr_id))
        if raw_edges != stored_edges:
            raise ValueError("Association-edge sets differ")
        result("Unique association-edge set", len(raw_edges), len(raw_edges & stored_edges), "Archived handling-table association identifiers")
        for flag, field in [("handled_flag", "ASPECTS OF NEA FEP HANDLED"),
                            ("unhandled_flag", "NEA FEP UNHANDLED BECAUSE"), ("comment_flag", "COMMENTS")]:
            handling[flag] = handling[field].map(clean).ne("").astype(int)
        grouped = handling.groupby(["pfep_id", "sr_id"], as_index=False).agg(
            handled_flag=("handled_flag", "max"), unhandled_flag=("unhandled_flag", "max"),
            comment_flag=("comment_flag", "max"), relation_rows=("source_record_id", "size"))
        flags = grouped.merge(net, on=["pfep_id", "sr_id"], suffixes=("_raw", "_stored"), validate="one_to_one")
        for flag in ["handled_flag", "unhandled_flag", "comment_flag", "relation_rows"]:
            result(flag, len(flags), int(flags[flag + "_raw"].astype(int).eq(flags[flag + "_stored"].astype(int)).sum()),
                   "Per-association nonempty raw field indicator; handled and unhandled indicators may coexist" if flag != "relation_rows" else "Raw relation-row multiplicity")
        cat = catalogue[["FEP NR", "FEP NAME", "MAIN CATEGORY", "CATEGORYNAME", "SYSTEM COMPONENT", "REVISION DATE"]].rename(columns={
            "FEP NR": "sr_id", "FEP NAME": "sr_name", "MAIN CATEGORY": "main_category", "CATEGORYNAME": "category",
            "SYSTEM COMPONENT": "system_component", "REVISION DATE": "revision_date"})
        for column in cat:
            cat[column] = cat[column].map(clean)
        stored_cat = pd.read_csv(data / "srsite_catalogue_407.csv", dtype=str, keep_default_na=False)
        pd.testing.assert_frame_equal(cat.sort_values("sr_id").reset_index(drop=True), stored_cat.sort_values("sr_id").reset_index(drop=True))
        result("SR-Site catalogue identifiers and metadata", len(cat), len(cat), "Stage-specific target catalogue")

        raw_snapshot = make_snapshot(temp, data)
        stored_snapshot = json.loads(SOURCE_SNAPSHOT.read_text())
        result("Declared raw-file hashes", len(required), sum(raw_snapshot["source_files"][name + ".KSE"]["sha256"] == stored_snapshot["source_files"][name + ".KSE"]["sha256"] for name in required), "Eight parsed FileMaker source tables")
        result("Complete coverage-source field records", len(raw_snapshot["records"]), sum(raw_snapshot["records"][pid] == stored_snapshot["records"][pid] for pid in raw_snapshot["records"]), "Imported fields, full mapping-field record, and retained handling rows")
        result("Target lookup tables", len(raw_snapshot["target_lookups"]), sum(raw_snapshot["target_lookups"][name] == stored_snapshot["target_lookups"][name] for name in raw_snapshot["target_lookups"]), "SR-Site process/variable/catalogue, SR-Can catalogue, and SAFE matrix lookups")
        result("PFEP target record identifiers", len(raw_snapshot["pfep_record_ids"]), sum(raw_snapshot["pfep_record_ids"][pid] == stored_snapshot["pfep_record_ids"][pid] for pid in raw_snapshot["pfep_record_ids"]), "Raw PROFEP record identifier for each catalogued PFEP")
        raw_records, raw_relations = build(raw_snapshot, json.loads(RULES.read_text()), data)
        for frame, filename, key, name in [
            (raw_records, "coverage_evidence_200.csv", "pfep_id", "Documentary evidence records"),
            (raw_relations, "provenance_relations.csv", "relation_id", "Provenance relations and literal evidence spans"),
        ]:
            stored = pd.read_csv(data / filename, dtype=str, keep_default_na=False)
            pd.testing.assert_frame_equal(frame.astype(str).sort_values(key).reset_index(drop=True), stored.sort_values(key).reset_index(drop=True))
            result(name, len(frame), len(frame), "Declared contextual interpretation and namespace/stage resolution rules; not independent adjudication")
    pd.DataFrame(checks).to_csv(data / "source_integrity_checks.csv", index=False)
    print(f"Verified archive hash and {len(checks)} source-integrity comparisons")
    return pd.DataFrame(checks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--data-directory", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    main(args.archive, args.data_directory)
