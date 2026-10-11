#!/usr/bin/env python3
"""Check the proposed record format, cross-field consistency and review tasks.

The format checker implements the keywords used by screening_record.schema.json.
It is not a general-purpose JSON Schema Draft 2020-12 implementation. Application
checks assess record consistency; technical review tasks require source inspection.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path


ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
KEYWORDS = {"$ref", "type", "const", "enum", "properties", "required",
            "additionalProperties", "items", "minLength", "minItems",
            "minimum", "format", "allOf", "anyOf", "if", "then"}


def issue(code: str, path: str, message: str) -> dict:
    return {"code": code, "path": path, "message": message}


def check_schema_keywords(schema: dict) -> None:
    """Reject unsupported constraints instead of silently accepting a new schema."""
    extra = set(schema) - ANNOTATIONS - KEYWORDS
    if extra:
        raise ValueError(f"Unsupported record schema keywords: {sorted(extra)}")
    if "$ref" in schema and not schema["$ref"].startswith("#/"):
        raise ValueError("Only local schema references are supported.")
    if "format" in schema and schema["format"] != "date":
        raise ValueError("Only the date format is supported.")
    for key in ("properties", "$defs"):
        for child in schema.get(key, {}).values():
            check_schema_keywords(child)
    for key in ("items", "if", "then"):
        if key in schema:
            check_schema_keywords(schema[key])
    for key in ("allOf", "anyOf"):
        for child in schema.get(key, []):
            check_schema_keywords(child)


def matches_type(value: object, name: str) -> bool:
    checks = {
        "object": lambda: isinstance(value, dict),
        "array": lambda: isinstance(value, list),
        "string": lambda: isinstance(value, str),
        "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
        "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": lambda: isinstance(value, bool),
        "null": lambda: value is None,
    }
    if name not in checks:
        raise ValueError(f"Unsupported schema type: {name}")
    return checks[name]()


def format_issues(value: object, schema: dict, root: dict, path: str = "$") -> list:
    out = []
    if "$ref" in schema:
        target = root
        for part in schema["$ref"][2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        out.extend(format_issues(value, target, root, path))
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(matches_type(value, t) for t in types):
            return out + [issue("format.type", path, f"Expected {' or '.join(types)}.")]
    if "const" in schema and value != schema["const"]:
        out.append(issue("format.const", path, f"Expected {schema['const']!r}."))
    if "enum" in schema and value not in schema["enum"]:
        out.append(issue("format.enum", path, "Value is outside the permitted categories."))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                out.append(issue("format.required", f"{path}.{key}", "Required field is absent."))
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in set(value) - set(props):
                out.append(issue("format.additional_property", f"{path}.{key}", "Field is outside the record contract."))
        for key, sub in props.items():
            if key in value:
                out.extend(format_issues(value[key], sub, root, f"{path}.{key}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            out.append(issue("format.min_items", path, "Array contains too few entries."))
        if "items" in schema:
            for i, item in enumerate(value):
                out.extend(format_issues(item, schema["items"], root, f"{path}[{i}]"))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            out.append(issue("format.min_length", path, "Text is shorter than the required length."))
        if schema.get("format") == "date":
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise ValueError()
                date.fromisoformat(value)
            except ValueError:
                out.append(issue("format.date", path, "Expected a valid calendar date in YYYY-MM-DD form."))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            out.append(issue("format.minimum", path, "Number is below the permitted minimum."))
    for sub in schema.get("allOf", []):
        out.extend(format_issues(value, sub, root, path))
    if "anyOf" in schema:
        if not any(not format_issues(value, sub, root, path) for sub in schema["anyOf"]):
            out.append(issue("format.any_of", path, "Value does not meet any permitted alternative."))
    if "if" in schema and not format_issues(value, schema["if"], root, path):
        if "then" in schema:
            out.extend(format_issues(value, schema["then"], root, path))
    return out


def application_checks(record: dict) -> tuple[list, list]:
    """Check references and status consistency without deciding physical coverage."""
    issues, tasks = [], []
    relations = record["relations"]
    ids = [r["relation_id"] for r in relations]
    for duplicate in sorted({rid for rid in ids if ids.count(rid) > 1}):
        issues.append(issue("application.duplicate_relation", "$.relations", f"Relation identifier {duplicate} occurs more than once."))
    by_id = {r["relation_id"]: r for r in relations}
    for i, relation in enumerate(relations):
        path = f"$.relations[{i}]"
        if relation["source"] != record["source"]:
            issues.append(issue("application.source_key", path + ".source", "Relation source differs from the record source key."))
        scope = relation["scope"]
        if scope["status"] == "specified" and (not scope["covered_aspects"] or not scope["justification"]):
            issues.append(issue("application.specified_scope", path + ".scope", "A specified scope requires covered aspects and a justification."))
        if scope["status"] == "unrecorded":
            tasks.append(issue("review.scope", path + ".scope", "Inspect the source and receiving tasks to document the represented aspects and any residual scope."))

    adoption = record["adoption"]
    for rid in adoption["adopted_relation_ids"]:
        relation = by_id.get(rid)
        if relation is None:
            issues.append(issue("application.adoption_reference", "$.adoption.adopted_relation_ids", f"Adopted relation {rid} is absent from this record."))
        elif adoption["status"] == "recorded":
            if not relation["targets"]:
                issues.append(issue("application.adopted_target", "$.adoption.adopted_relation_ids", f"Adopted relation {rid} has no identified target."))
            if relation["scope"]["status"] != "specified":
                issues.append(issue("application.adopted_scope", "$.adoption.adopted_relation_ids", f"Adopted relation {rid} lacks a specified scope."))
    if record["screening"]["outcome"] == "coverage_elsewhere" and adoption["status"] == "unrecorded":
        tasks.append(issue("review.disposition", "$.adoption", "Inspect the screening basis for adopted relations or a documented aggregate disposition, preserving the recorded screening authorities."))
    if record["screening"]["outcome"] == "inapplicable" and not record["applicability_premises"]:
        tasks.append(issue("review.applicability", "$.applicability_premises", "Identify the waste, design or site premise that limits applicability and its specification version."))
    if record["source_aggregation"]["level"] == "unrecorded":
        tasks.append(issue("review.aggregation", "$.source_aggregation", "Determine the source entry's aggregation from source content and screening context before requesting an individual process destination."))
    for i, change in enumerate(record["stage_changes"]):
        path = f"$.stage_changes[{i}]"
        if change["relation_id"] not in by_id:
            issues.append(issue("application.stage_reference", path + ".relation_id", "Stage change refers to a relation absent from this record."))
        if change["disposition"] == "superseded" and change["successor"] is None:
            issues.append(issue("application.stage_successor", path + ".successor", "A superseded relation requires an identified successor."))
        if change["successor"] is not None and change["successor"]["assessment_stage"] != change["to_stage"]:
            issues.append(issue("application.successor_stage", path + ".successor", "Successor assessment stage differs from the declared receiving stage."))
    for i, lead in enumerate(record["retrieval_leads"]):
        if lead["rank"] > lead["eligible_pool_size"]:
            issues.append(issue("application.retrieval_rank", f"$.retrieval_leads[{i}]", "Candidate rank exceeds the eligible candidate population."))
    return issues, tasks


def check_record(record: object, schema: dict) -> dict:
    check_schema_keywords(schema)
    structural = format_issues(record, schema, schema)
    application, tasks = ([], []) if structural else application_checks(record)
    return {"format_valid": not structural, "format_issues": structural,
            "application_issues": application, "technical_review_tasks": tasks}


def reject_non_json_number(value: str) -> None:
    raise ValueError(f"Non-JSON numeric value: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--schema", type=Path,
                        default=Path(__file__).resolve().parents[2] / "specifications/screening_record.schema.json")
    args = parser.parse_args()
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    try:
        record = json.loads(args.record.read_text(encoding="utf-8"), parse_constant=reject_non_json_number)
    except (json.JSONDecodeError, ValueError) as exc:
        result = {"format_valid": False,
                  "format_issues": [issue("format.json_syntax", "$", str(exc))],
                  "application_issues": [], "technical_review_tasks": []}
    else:
        result = check_record(record, schema)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["format_valid"] and not result["application_issues"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
