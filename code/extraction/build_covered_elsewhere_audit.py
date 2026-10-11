#!/usr/bin/env python3
"""Reconstruct documentary provenance for the 200 coverage-related exclusions.

The declared source snapshot preserves the archived fields. Documentary rules
record textual interpretations and literal evidence spans; deterministic code
resolves identifiers in their stated namespace and assessment stage. Target
existence, reference semantics and SKB adoption are distinct variables. No
retrieval score, exact-title hypothesis or independent adjudication is used to
assign a documentary class.

python code/extraction/build_covered_elsewhere_audit.py
python code/extraction/build_covered_elsewhere_audit.py --raw-directory PATH
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DATA = ROOT / "data"
sys.path.insert(0, str(HERE))
from fp5_miniparser import FP5MiniParser, decode_vli

ENC = "mac_roman"
SOURCE_SNAPSHOT = HERE / "documentary_source_snapshot.json"
RULES = HERE / "documentary_rules.json"
STRICT_SEMANTICS = {
    "covered_by", "treated_in", "split_into", "lumped_into", "duplicate_of",
    "aspects_examined_in", "aspects_discussed_elsewhere", "replacement_cross_reference",
}
ASSOCIATION_SEMANTICS = STRICT_SEMANTICS | {
    "see_also", "related_discussion", "specific_factor_reference",
    "historical_named_treatment", "historical_partial_treatment",
    "structured_process_association", "structured_variable_association",
    "structured_biosphere_association", "retained_handling_association",
}


def clean(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean(value)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def byte_value(value: object) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, list):
        return b"".join(byte_value(x) for x in value)
    if isinstance(value, dict) and b"\x01" in value:
        return byte_value(value[b"\x01"])
    return b""


def parse_filemaker(path: Path) -> pd.DataFrame:
    parser = FP5MiniParser(path)
    tree = parser.parse_tree()
    schema = {
        key.decode(ENC, errors="replace"): value[1:1 + value[0]]
        for key, value in tree[b"\x03"][b"\x01"].items()
        if isinstance(value, bytes) and value
    }
    rows = []
    for rid, record in tree[b"\x05"].items():
        row = {"source_record_id": str(decode_vli(rid))}
        row.update({name: byte_value(record.get(fid)).decode(ENC, errors="replace").replace("\x00", "")
                    for name, fid in schema.items()})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("source_record_id", key=lambda x: x.astype(int)).reset_index(drop=True)


def numeric_key(pfep_id: str) -> str | None:
    match = re.fullmatch(r"\s*([A-Z])\s+(\d+(?:\.\d+)*)\s*", pfep_id)
    if not match:
        return None
    return match[1] + " " + ".".join(str(int(x)) for x in match[2].split("."))


def make_snapshot(raw_directory: Path, data_directory: Path = DATA) -> dict:
    """Read declared raw tables; omitted record fields are explicitly empty."""
    nr = pd.read_csv(data_directory / "not_relevant_370_normalized.csv", dtype=str, keep_default_na=False)
    source_ids = set(nr.loc[nr.covered_by_other_feps_flag.eq("1"), "pfep_id"])
    names = ["NEA mapping_SRSite", "PROFEP", "HandlingNEAFEPs_SRSite", "Processes_SRSite",
             "Variables_SRSite", "SR_Site_FEP_catalogue", "SR_Can_FEP_catalogue", "SAFEbiomatrix"]
    tables = {name: parse_filemaker(raw_directory / (name + ".KSE")) for name in names}
    mapping = {clean(row["NEA PROJECT FEP ID"]): row for row in tables["NEA mapping_SRSite"].to_dict("records")}
    imported = {clean(row["UNIQUE NO."]): row for row in tables["PROFEP"].to_dict("records")}
    keep_imported = ["source_record_id", "UNIQUE NO.", "FEP NAME", "FEP DESCRIPTION", "COMMENTS",
                     "PROJECT LETTER", "PROJECT TITLE", "PROJECT REFERENCE"]
    records = {}
    for pid in sorted(source_ids):
        records[pid] = {
            "PROFEP.KSE": {key: imported[pid].get(key, "") for key in keep_imported},
            "NEA mapping_SRSite.KSE": {key: value for key, value in mapping[pid].items() if value != ""},
            "HandlingNEAFEPs_SRSite.KSE": [r for r in tables["HandlingNEAFEPs_SRSite"].to_dict("records")
                                            if clean(r["NEA PROJECT FEP ID"]) == pid],
        }
    target_fields = {
        "Processes_SRSite": ["source_record_id", "PROCESS NUMBER", "PROCESS NAME", "SYSTEM COMPONENT", "VERSION", "REVISION DATE"],
        "Variables_SRSite": ["source_record_id", "VARIABLE NUMBER", "VARIABLE NAME", "SYSTEM COMPONENT", "VERSION", "REVISION DATE"],
        "SR_Site_FEP_catalogue": ["source_record_id", "FEP NR", "FEP NAME", "VERSION", "REVISION DATE", "DESCRIPTION"],
        "SR_Can_FEP_catalogue": ["source_record_id", "FEP NR", "FEP NAME", "VERSION", "REVISION DATE", "DESCRIPTION"],
        "SAFEbiomatrix": ["source_record_id", "ELEMENT NUMBER:", "IDENTIFICATION IN MATRIX:", "DESCRIPTION:"],
    }
    return {
        "schema_version": "2.0",
        "source_files": {name + ".KSE": {
            "sha256": hashlib.sha256((raw_directory / (name + ".KSE")).read_bytes()).hexdigest(),
            "records_in_table": len(tables[name]), "field_names": list(tables[name].columns),
        } for name in names},
        "empty_field_convention": "Absent keys in a stored source record denote empty archived fields; field_names supplies the complete schema.",
        "records": records,
        "pfep_record_ids": {pid: row["source_record_id"] for pid, row in imported.items()},
        "target_lookups": {name + ".KSE": tables[name][fields].to_dict("records") for name, fields in target_fields.items()},
    }


def build(snapshot: dict, rules: dict, data_directory: Path = DATA) -> tuple[pd.DataFrame, pd.DataFrame]:
    pop = pd.read_csv(data_directory / "pfep_relevance_population_1671.csv", dtype=str, keep_default_na=False)
    nr = pd.read_csv(data_directory / "not_relevant_370_normalized.csv", dtype=str, keep_default_na=False)
    sources = nr[nr.covered_by_other_feps_flag.eq("1")].copy()
    if len(sources) != 200 or set(sources.pfep_id) != set(snapshot["records"]) or set(sources.pfep_id) != set(rules["records"]):
        raise ValueError("Every coverage source requires one source snapshot and one record interpretation.")
    population = {row["pfep_id"]: row for row in pop.to_dict("records")}
    keys = defaultdict(list)
    titles = defaultdict(list)
    for pid, row in population.items():
        keys[numeric_key(pid)].append(row)
        titles[(row["project_letter"], norm(row["pfep_name"]))].append(row)
    lookups = snapshot["target_lookups"]
    cat_by_stage = {stage: {clean(r["FEP NR"]): r for r in lookups[name]} for stage, name in [
        ("SR-Site", "SR_Site_FEP_catalogue.KSE"), ("SR-Can", "SR_Can_FEP_catalogue.KSE")]}
    relations = []

    def add(pid: str, source_file: str, field: str, value: str, span: str,
            semantics: str, layer: str, stage: str, **extra):
        if span not in value:
            raise ValueError(f"Evidence span absent from source field: {pid} {field}: {span!r}")
        start = value.index(span)
        metadata = snapshot["records"][pid].get(source_file, {})
        mapping_context = snapshot["records"][pid]["NEA mapping_SRSite.KSE"]
        inventory_context = snapshot["records"][pid]["PROFEP.KSE"]
        row = {
            "source_pfep_id": pid, "source_pfep_name": population[pid]["pfep_name"],
            "project_letter": population[pid]["project_letter"],
            "source_inventory_reference": inventory_context.get("PROJECT REFERENCE", ""),
            "source_inventory_title": inventory_context.get("PROJECT TITLE", ""),
            "source_nea_database_version": mapping_context.get("NEA DATABASE VERSION", ""),
            "source_mapping_version": mapping_context.get("DATABASE VERSION", ""),
            "source_mapping_revision_date": mapping_context.get("REVISION DATE", ""),
            "raw_source_file": source_file,
            "raw_source_sha256": snapshot["source_files"][source_file]["sha256"],
            "source_record_id": metadata.get("source_record_id", "") if isinstance(metadata, dict) else "",
            "source_field": field, "source_field_sha256": hashlib.sha256(value.encode()).hexdigest(),
            "evidence_span": span, "span_start": start, "span_end": start + len(span),
            "origin_layer": layer, "relation_semantics": semantics, "stage": stage,
            "relation_direction": "source_to_target", "direction_valid": 1,
            "target_type": "", "target_id": "", "target_name": "", "target_literal": "",
            "identifier_resolution": "", "target_source_file": "", "target_source_record_id": "",
            "target_stage": stage, "target_revision_date": "", "target_exists_in_stage": "unknown",
            "target_relevance": "not_applicable", "target_present_in_srsite_catalogue": "not_applicable",
            "candidate_target_ids": "", "candidate_count": 0, "ambiguity": "none",
            "explicit_destination": 0, "reference_verified": 0, "coverage_endpoint": 0,
            "skb_adoption_documented": 0, "current_skb_adoption_documented": 0,
            "scope_rationale_present": 0, "benchmark_eligible": 0, "status_conflict": 0,
            "interpretation_rationale": "",
        }
        row.update(extra)
        row["target_source_sha256"] = snapshot["source_files"].get(row["target_source_file"], {}).get("sha256", "")
        row["coverage_endpoint"] = int(semantics in STRICT_SEMANTICS and row["direction_valid"] == 1)
        row["benchmark_eligible"] = int(
            row["target_type"] == "PFEP" and row["coverage_endpoint"] == 1 and row["reference_verified"] == 1
            and row["target_relevance"].lower() == "relevant" and row["ambiguity"] == "none")
        row["relation_id"] = "R-" + hashlib.sha256(json.dumps(
            [pid, source_file, field, start, span, semantics, row["target_type"], row["target_id"], row["target_literal"]],
            ensure_ascii=False).encode()).hexdigest()[:16]
        relations.append(row)

    def pfep_reference(pid: str, rule: dict):
        source_file = rule.get("source_file", "PROFEP.KSE")
        field = rule.get("source_field", "FEP DESCRIPTION")
        raw = snapshot["records"][pid][source_file].get(field, "")
        span = rule["span"]
        project = population[pid]["project_letter"]
        for token in rule["targets"]:
            if isinstance(token, str):
                token = {"literal": token}
            literal = token["literal"]
            if literal not in span:
                raise ValueError(f"Target literal absent from evidence span: {pid} {literal}")
            mode = token.get("mode", rule.get("mode", "numeric"))
            if mode == "numeric":
                if not re.fullmatch(r"\d+(?:\.\d+)*", literal) or not re.search(
                    r"(?<![\d.])" + re.escape(literal) + r"(?!\d|\.\d)", span
                ):
                    raise ValueError(f"A local identifier must be a whole numeric token: {pid} {literal}")
                # Numeric conversion is allowed only inside interpreted reference
                # spans. A bare measurement or numbered prose list is not a FEP cue.
                candidates = keys.get(numeric_key(project + " " + literal), [])
            elif mode == "name":
                candidates = titles.get((project, norm(literal)), [])
            else:
                raise ValueError(mode)
            prefixes = token.get("prefixes", rule.get("prefixes", []))
            if prefixes:
                candidates = [r for r in candidates if any(r["pfep_id"].startswith(prefix) for prefix in prefixes)]
            multiple_explicit_namespaces = bool(prefixes and rule.get("explicit_multiple_namespaces", False))
            ambiguous = len(candidates) > 1 and not multiple_explicit_namespaces
            shared = {
                "target_type": "PFEP", "target_literal": literal,
                "identifier_resolution": "source_inventory_local_number" if mode == "numeric" else "source_inventory_named_reference",
                "target_source_file": "PROFEP.KSE",
                "candidate_target_ids": "; ".join(sorted(r["pfep_id"] for r in candidates)),
                "candidate_count": len(candidates),
                "ambiguity": "multiple_source_inventory_records" if ambiguous else ("unresolved_reference" if not candidates else "none"),
                "relation_direction": rule.get("relation_direction", "source_to_target"),
                "direction_valid": rule.get("direction_valid", 1),
                "interpretation_rationale": rule["rationale"],
                "explicit_destination": int(rule["semantics"] in ASSOCIATION_SEMANTICS),
            }
            for target in candidates or [None]:
                detail = dict(shared)
                if target:
                    detail.update(target_id=target["pfep_id"], target_name=target["pfep_name"],
                                  target_exists_in_stage="yes", target_relevance=target["relevance"],
                                  target_source_record_id=snapshot["pfep_record_ids"][target["pfep_id"]],
                                  reference_verified=int(not ambiguous and rule.get("direction_valid", 1) == 1))
                else:
                    detail.update(target_name=literal, target_exists_in_stage="no")
                add(pid, source_file, field, raw, span, rule["semantics"],
                    rule.get("origin_layer", "original_inventory"), rule.get("stage", "original_inventory"), **detail)

    for source in sources.to_dict("records"):
        pid = source["pfep_id"]
        rec = snapshot["records"][pid]
        mapping = rec["NEA mapping_SRSite.KSE"]
        decision = rules["records"][pid]
        for rule in decision.get("references", []):
            pfep_reference(pid, rule)

        # Structured fields identify an association retained in the SR-Site
        # table. A process/variable name is qualified by system component when
        # that context is supplied; association does not establish final adoption.
        for field, table, typ, name_field, id_field in [
            ("SELECTED PROCESS", "Processes_SRSite.KSE", "SKB_PROCESS", "PROCESS NAME", "PROCESS NUMBER"),
            ("PROCESS LIST", "Processes_SRSite.KSE", "SKB_PROCESS", "PROCESS NAME", "PROCESS NUMBER"),
            ("SELECTED VARIABLE", "Variables_SRSite.KSE", "SKB_VARIABLE", "VARIABLE NAME", "VARIABLE NUMBER"),
            ("VARIABLE LIST", "Variables_SRSite.KSE", "SKB_VARIABLE", "VARIABLE NAME", "VARIABLE NUMBER"),
        ]:
            raw = mapping.get(field, "")
            for literal in [x.strip() for x in re.split(r"[\r\n;]+", raw) if x.strip()]:
                candidates = [r for r in lookups[table] if norm(r[name_field]) == norm(literal)]
                component = clean(mapping.get("SYSTEM COMPONENT", ""))
                if component:
                    candidates = [r for r in candidates if norm(r["SYSTEM COMPONENT"]) == norm(component)]
                for target in candidates or [None]:
                    target_id = clean(target[id_field]) if target else ""
                    add(pid, "NEA mapping_SRSite.KSE", field, raw, literal,
                        "structured_process_association" if typ == "SKB_PROCESS" else "structured_variable_association",
                        "skb_structured_field", "SR-Site", target_type=typ, target_id=target_id,
                        target_name=clean(target[name_field]) if target else literal, target_literal=literal,
                        identifier_resolution="exact_name_and_component" if component else "exact_name",
                        target_source_file=table, target_source_record_id=target["source_record_id"] if target else "",
                        target_stage=clean(target["VERSION"]) if target else "SR-Site",
                        target_revision_date=clean(target["REVISION DATE"]) if target else "",
                        target_exists_in_stage="yes" if target else "no", candidate_count=len(candidates),
                        candidate_target_ids="; ".join(sorted(clean(t[id_field]) for t in candidates)),
                        ambiguity="none" if len(candidates) == 1 else ("multiple_named_records" if candidates else "unresolved_reference"),
                        explicit_destination=1, reference_verified=int(len(candidates) == 1),
                        target_present_in_srsite_catalogue="yes" if target_id in cat_by_stage["SR-Site"] else "no",
                        interpretation_rationale="A retained selection/list field records an association. Lookup is qualified by the archived system component where supplied; the field alone supplies no coverage-scope or final-adoption statement.")

        for field, stage in [("SRSITEBIOSPHEREFEP LIST", "SR-Site"), ("SRCANBIOSPHEREFEP LIST", "SR-Can"),
                             ("SRCANBIOSPHEREFEP LIST COPY", "SR-Can")]:
            raw = mapping.get(field, "")
            for token in re.findall(r"\b(?:CompBio|ProvBio|Bio)\d+\b", raw):
                target = cat_by_stage[stage].get(token)
                add(pid, "NEA mapping_SRSite.KSE", field, raw, token, "structured_biosphere_association",
                    "skb_structured_field", stage, target_type="SR_FEP", target_id=token,
                    target_literal=token, target_name=clean(target["FEP NAME"]) if target else "",
                    identifier_resolution="literal_stage_qualified_id", target_source_file="SR_Can_FEP_catalogue.KSE" if stage == "SR-Can" else "SR_Site_FEP_catalogue.KSE",
                    target_source_record_id=target["source_record_id"] if target else "",
                    target_revision_date=clean(target["REVISION DATE"]) if target else "",
                    target_exists_in_stage="yes" if target else "no", candidate_count=int(target is not None),
                    candidate_target_ids=token if target else "", explicit_destination=1, reference_verified=int(target is not None),
                    ambiguity="none" if target else "unresolved_reference",
                    target_present_in_srsite_catalogue="yes" if token in cat_by_stage["SR-Site"] else "no",
                    status_conflict=int(pid == "W 1.072"),
                    interpretation_rationale=("The source field names SR-Can; its provisional category record exists in the SR-Can catalogue. No SR-Site lineage is specified." if stage == "SR-Can" else "The SR-Site biosphere field retains a target despite the source's excluded status; the discussion records reclassification in 2010."))

        for handled in rec["HandlingNEAFEPs_SRSite.KSE"]:
            target_id = clean(handled["SRSITE FEP ID"])
            target = cat_by_stage["SR-Site"].get(target_id)
            add(pid, "HandlingNEAFEPs_SRSite.KSE", "SRSITE FEP ID", handled["SRSITE FEP ID"], handled["SRSITE FEP ID"],
                "retained_handling_association", "skb_handling_table", "SR-Site",
                source_record_id=handled["source_record_id"], target_type="SR_FEP", target_id=target_id,
                target_name=clean(target["FEP NAME"]) if target else clean(handled["SRSITE FEP NAME"]),
                target_literal=target_id, identifier_resolution="literal_stage_qualified_id",
                target_source_file="SR_Site_FEP_catalogue.KSE", target_source_record_id=target["source_record_id"] if target else "",
                target_exists_in_stage="yes" if target else "no", candidate_count=int(target is not None),
                target_revision_date=clean(target["REVISION DATE"]) if target else "",
                target_present_in_srsite_catalogue="yes" if target else "no", explicit_destination=1,
                reference_verified=int(target is not None), status_conflict=1,
                interpretation_rationale="The archived handling table retains this edge although the same source is excluded in the screening table. A retained edge does not by itself establish a current coverage decision.")

        for rule in decision.get("other_relations", []):
            source_file = rule.get("source_file", "NEA mapping_SRSite.KSE")
            field = rule.get("source_field", "COMMENTS NEEDS DISCUSSION")
            raw = rec[source_file].get(field, "")
            extra = {k: v for k, v in rule.items() if k not in ["source_file", "source_field", "span", "semantics", "origin_layer", "stage"]}
            add(pid, source_file, field, raw, rule["span"], rule["semantics"], rule.get("origin_layer", "skb_screening_discussion"), rule["stage"], **extra)

    rel = pd.DataFrame(relations)
    if rel.relation_id.duplicated().any():
        raise ValueError("Duplicate provenance relation identifiers")
    record_rows = []
    for source in sources.to_dict("records"):
        pid = source["pfep_id"]
        fields = snapshot["records"][pid]
        imported = fields["PROFEP.KSE"]
        mapping = fields["NEA mapping_SRSite.KSE"]
        decision = rules["records"][pid]
        local = rel[rel.source_pfep_id.eq(pid)]
        association = local[local.relation_semantics.isin(ASSOCIATION_SEMANTICS) & local.direction_valid.eq(1)]
        current = association[association.origin_layer.str.startswith("skb_") & association.stage.eq("SR-Site")]
        historical = association[association.origin_layer.str.startswith("skb_") & ~association.stage.eq("SR-Site")]
        original = association[association.origin_layer.eq("original_inventory")]
        resolved = association[association.target_exists_in_stage.eq("yes") & association.ambiguity.eq("none")]
        strict = local[local.coverage_endpoint.eq(1) & local.reference_verified.eq(1)]
        rationale = clean(mapping.get("COMMENTS NEEDS DISCUSSION", "")) or clean(mapping.get("ASSESSMENT BASIS COMMENT", ""))
        if len(current):
            documentary_class = "SR-Site-stage SKB association"
        elif len(historical):
            documentary_class = "Earlier-stage SKB association"
        elif len(original):
            documentary_class = "Original-inventory reference"
        elif rationale:
            documentary_class = "SKB rationale without identifiable destination"
        else:
            documentary_class = "No identifiable documentary destination"
        relevant_resolved = resolved[resolved.target_type.ne("PFEP") | resolved.target_relevance.str.lower().eq("relevant")]
        row = {
            "pfep_id": pid, "pfep_name": source["pfep_name"], "project_letter": source["project_letter"],
            "reason": source["relevance_motivation_clean"], "documentary_class": documentary_class,
            "formal_reason_coverage_assertion": 1,
            "documentary_unresolved": int(resolved.empty),
            "no_resolved_relevant_destination": int(relevant_resolved.empty),
            "imported_text_present": int(bool(clean(imported.get("FEP DESCRIPTION", "")) or clean(imported.get("COMMENTS", "")))),
            "imported_description_present": int(bool(clean(imported.get("FEP DESCRIPTION", "")))),
            "imported_comments_present": int(bool(clean(imported.get("COMMENTS", "")))),
            "skb_explanatory_rationale_present": int(bool(rationale)),
            "skb_discussion_coverage_assertion_present": int(decision.get("skb_discussion_coverage_assertion_present", 0)),
            "skb_discussion_targeted_assertion_present": int(decision.get("skb_discussion_targeted_assertion_present", 0)),
            "skb_discussion_scope_rationale_present": int(decision.get("skb_discussion_scope_rationale_present", 0)),
            "skb_adoption_documented": int(local.skb_adoption_documented.max()) if len(local) else 0,
            "current_skb_adoption_documented": int(local.current_skb_adoption_documented.max()) if len(local) else 0,
            "current_association_present": int(len(current) > 0), "historical_association_present": int(len(historical) > 0),
            "original_inventory_reference_present": int(len(original) > 0),
            "original_inventory_coverage_reference_present": int(len(strict[strict.origin_layer.eq("original_inventory")]) > 0),
            "ambiguous_reference_present": int(local.ambiguity.str.startswith("multiple_").any()) if len(local) else 0,
            "reference_resolution_issue_present": int(local.ambiguity.ne("none").any()) if len(local) else 0,
            "unresolved_reference_present": int(local.target_exists_in_stage.eq("no").any()) if len(local) else 0,
            "unverified_reference_present": int(local.target_exists_in_stage.eq("unknown").any()) if len(local) else 0,
            "status_conflict_present": int(local.status_conflict.max()) if len(local) else 0,
            "n_relations": len(local), "n_unique_resolved_destinations": len(resolved[["target_type", "target_id", "target_stage"]].drop_duplicates()),
            "n_current_association_destinations": len(current[["target_type", "target_id", "target_name"]].drop_duplicates()),
            "n_historical_association_destinations": len(historical[["target_type", "target_id", "target_name"]].drop_duplicates()),
            "n_original_inventory_reference_destinations": len(original[["target_type", "target_id", "target_name"]].drop_duplicates()),
            "n_benchmark_destinations": local.loc[local.benchmark_eligible.eq(1), "target_id"].nunique(),
            "resolved_destination_ids": "; ".join(sorted(set(resolved.target_id) - {""})),
            "benchmark_destination_ids": "; ".join(sorted(set(local.loc[local.benchmark_eligible.eq(1), "target_id"]))),
            "imported_description_raw": imported.get("FEP DESCRIPTION", ""), "imported_comments_raw": imported.get("COMMENTS", ""),
            "skb_discussion_raw": mapping.get("COMMENTS NEEDS DISCUSSION", ""),
            "skb_assessment_basis_raw": mapping.get("ASSESSMENT BASIS COMMENT", ""),
            "mapping_revision_date": mapping.get("REVISION DATE", ""), "mapping_database_version": mapping.get("DATABASE VERSION", ""),
            "mapping_state_raw": mapping.get("MAPPING", ""),
            "source_fields_json": json.dumps(fields, ensure_ascii=False, sort_keys=True),
            "interpretation_rationale": decision["rationale"],
        }
        record_rows.append(row)
    return pd.DataFrame(record_rows).sort_values("pfep_id"), rel.sort_values(["source_pfep_id", "origin_layer", "source_field", "span_start", "target_id"])


def main(raw_directory=None, output_directory=DATA, source_snapshot=SOURCE_SNAPSHOT, rules_path=RULES):
    snapshot = make_snapshot(Path(raw_directory)) if raw_directory else json.loads(Path(source_snapshot).read_text())
    rules = json.loads(Path(rules_path).read_text())
    records, relations = build(snapshot, rules)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    records.to_csv(output_directory / "coverage_evidence_200.csv", index=False)
    relations.to_csv(output_directory / "provenance_relations.csv", index=False)
    print(records.documentary_class.value_counts().to_string())
    print(f"Sources={len(records)}; evidence relations={len(relations)}; strict reference sources={(records.n_benchmark_destinations > 0).sum()}")
    return records, relations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-directory", type=Path)
    parser.add_argument("--output-directory", type=Path, default=DATA)
    parser.add_argument("--source-snapshot", type=Path, default=SOURCE_SNAPSHOT)
    parser.add_argument("--rules", type=Path, default=RULES)
    args = parser.parse_args()
    main(args.raw_directory, args.output_directory, args.source_snapshot, args.rules)
