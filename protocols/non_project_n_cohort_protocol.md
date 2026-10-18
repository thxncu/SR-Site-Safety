# Non-Project N coverage-record census

## Population and unit

A feature, event or process is abbreviated FEP; a project FEP is abbreviated PFEP. The unit is a PFEP record with a formal screening reason that assigns its scope to other PFEPs. The source-qualified population contains 200 such records. The census selects every record whose stored project letter differs from N. Selection yields 55 unique records from A, E, H, I, J, M, S and W. Project K is retained as a zero-coverage row in the inventory summary. The census is exhaustive within this stated stratum.

The stratum is called the **non-Project N cohort**. It combines project or concept inventories, the repository-type encyclopedia represented by inventory E and two project or site inventories. It includes organizational headings and broader technical aggregations. Its 20 formal “Heading only” reasons and 35 “Too general” reasons are reported separately. Nonempty source text is a description of record content, not a measure of engineering detail or safety importance.

## Fields and evidence

The census joins `coverage_evidence_200.csv`, the normalized excluded-record table, the full PFEP population, the source inventory profiles, the provenance-relation register, the SR-Site catalogue and the existing auxiliary-search outcome table by unique identifiers. Imported description and comments, Swedish Nuclear Fuel and Waste Management Company (SKB) discussion and assessment basis, selected processes and variables, formal screening reasons, relation IDs and resolution flags are retained. The joins do not alter the source classifications.

The class labels identify the strongest available layer of documentary evidence. A named association can remain unresolved if the archive cannot distinguish its destination. Conversely, a source can have resolvable imported references even when a retained selected SKB variable does not resolve. Consequently, class counts and record-level resolution counts are reported separately.

`documentary_unresolved` means that no association is uniquely resolvable under the declared documentary rules. `no_resolved_relevant_destination` applies the additional requirement that a PFEP destination be finally relevant, or that a non-PFEP destination resolve in its stage-qualified catalogue. J 5.18 resolves to J 4.2.05, which is excluded; the two flags therefore differ for that source. Neither flag is a measure of scenario completeness or a physical performance calculation.

## Engineering domains

Domain summaries derive from stored International FEP (IFEP) identifiers and names. Prefixes 2.1, 2.2 and 2.3 identify wastes/engineered barriers, the geosphere and the surface environment. Prefixes in groups 0, 1 and 3 identify assessment issues, external or implementation factors, and contaminant/exposure factors. The exact prefix map is in the script. A source may have more than one domain, so domain counts overlap and do not sum to 55. E SFL-00 has no usable IFEP identifier and is reported separately. The domain grouping provides an entry point to source text; it is not an independently assigned safety-function or risk classification.

## Follow-up records

The 19 unresolved records are provided in a separate table. Its `proposed_record_check` column is an analytical recommendation, distinguished from archived fields. The recommended follow-up depends on the recorded issue: specify the represented scope or receiving tasks, preserve and qualify the existing rationale, or resolve a stage-qualified historical matrix element. A heading may be documented by its membership in a represented child set rather than by an artificial one-to-one physical-process link.

## Inventory association

Inventory-by-relevance tables are computed for all 1,671 records and for the 1,525 records outside Project N. Both ordinary and bias-corrected Cramér's V are reported. The correction follows Bergsma (2013), DOI: 10.1016/j.jkss.2012.10.002. Pearson chi-square cell contributions describe which inventory rows account for the full-table association. The census does not use a significance threshold or treat removal of an inventory as a causal intervention.

## Reproduction

Run from the package directory:

```bash
python code/compute_cohort_and_retrieval_checks.py --package . --output data
python code/test_cohort_retrieval_checks.py --package . --output data
```

Input checksums and the derived-file manifest identify the exact tables. The source code accepts explicit package and output paths. The source tables are read-only inputs.
