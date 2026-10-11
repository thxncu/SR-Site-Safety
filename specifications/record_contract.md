# Proposed screening record contract

The JavaScript Object Notation (JSON) schema and application programming interface (API) contract express the six record checks in manuscript Table 5. They specify a record store and review tasks that a safety-case owner could implement. The files do not describe a deployed service or an integration with an existing digital safety-case program.

## Source scope and decision provenance

`source` identifies the imported entry, its catalogue version and the assessment in which it was screened. `source_aggregation` records whether source content describes a heading, an umbrella entry, a broad description or an individual entry. The aggregation is qualified by evidence; a numeric parent identifier alone does not determine the appropriate screening unit. `mapping_context` records the receiving assessment component separately. A null source component preserves an unspecified source scope.

`screening.authorities` and `screening.authority_locator` preserve the people or bodies explicitly credited with screening. `adoption` concerns the decision to use particular relations as the basis of that disposition. A recorded screening authority does not establish which of several observed relations was adopted. Each relation preserves its direction, origin, endpoint key, literal source field and scope. Multiple source-field occurrences can point to the same endpoint without representing different physical processes.

The H 1.6.3 example uses the archived source record, mapping-table record 716. The source catalogue version is Version 2.1. The source component is unspecified; the receiving mapping and the Bu13 target both identify Buffer. The discussion calls the source a very general or super FEP. The screening field names Allan Hedin, Johan Andersson and Kristina Skagius. The example retains those names and their source locator while leaving relation adoption and scope unrecorded. Two relation occurrences preserve the separate PROCESS LIST and SELECTED PROCESS fields. These values are available in `code/extraction/documentary_source_snapshot.json` and `data/provenance_relations.csv`.

## Format, application consistency and technical review

Run the local checker from the package root:

```sh
python code/record_checks/check_screening_record.py specifications/observed_H_1_6_3.json
python -m unittest discover -s code/record_checks -p 'test_*.py'
```

The checker reports three distinct outputs. `format_issues` concern JSON syntax and the types, required fields, categories and date constraints used by the supplied schema. The standard-library implementation supports the keywords used by this specific contract and rejects unsupported schema keywords; it is not a general JSON Schema implementation. `application_issues` concern cross-field consistency, such as a nonexistent adopted relation, a superseded relation without a successor or a candidate rank beyond the eligible pool. `technical_review_tasks` identify source inspection still required to document scope, aggregate disposition or applicability premises.

An archived record with unrecorded scope or adoption can pass the format and application checks. Its review tasks preserve those unknowns. The checker's exit status is zero when record format and application consistency pass, including when technical review tasks remain. No check computes radionuclide release, establishes scenario completeness or certifies the technical adequacy of the screening decision.

The OpenAPI file specifies the shape of a possible retrieval endpoint and a record-check response. Implementing a service would also require record-store access, catalogue resolution, authentication, version transactions and a defined human review process. Those functions are outside the local checker. The schema version is 1.0.0; the accompanying research package version is 2.1.0.
