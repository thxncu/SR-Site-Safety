# Documentary provenance protocol

## Scope and inputs

The cohort is the 200 records in the archived SKB SR-Site screening table whose formal motivation attributes exclusion to coverage by other NEA project FEPs. This is a study of those records and their available documentary associations, not a claim that every source inventory or every safety-case document is complete.

Each source is examined on the same field set: the imported `PROFEP.KSE` description and comments; the screening motivation, discussion, assessment-basis and full mapping-field record in `NEA mapping_SRSite.KSE`; and any source-specific rows in `HandlingNEAFEPs_SRSite.KSE`. The snapshot preserves the full mapping schema. Omitted keys in its mapping records denote empty archived fields, not fields that were not examined. The 200-row output preserves the source fields as JSON and exposes the principal text fields as separate columns. A source without an identifiable destination remains in the record table even when it has no relation rows.

`documentary_source_snapshot.json` contains decoded source fields and the lookup fields needed to verify target identity. File hashes, raw table record identifiers, original-inventory references, mapping versions and dates retain the source context. The snapshot can be reconstructed directly from the official runtime archive. `documentary_rules.json` contains the record-level textual interpretations and literal evidence spans. These interpretations are declared research inputs, not independently adjudicated observations. Deterministic code applies the same namespace, stage, ambiguity and classification rules to those inputs.

## Units and documentary classes

The record unit is one excluded PFEP. The relation unit is one typed statement or structured-field occurrence identifying an association, reference or other contextual relation. Several fields may repeat the same target. Relation-row counts therefore differ from counts of unique source–target pairs or sources with evidence. No semantic score or inferred title/hierarchy match can promote a documentary class.

Classes are mutually exclusive labels of the highest applicable documentary source layer, in this order:

| Class | Rule | What it does not establish |
|---|---|---|
| SR-Site-stage SKB association | An SR-Site process, variable, biosphere or handling field retains a named or numbered association. | A retained field need not be a resolved identifier, an affirmative final adoption decision or a complete treatment of the excluded source. |
| Earlier-stage SKB association | A stage-qualified earlier SKB field or discussion names an SR-Can or SAFE destination or interaction family. | A historical pointer does not supply a current SR-Site lineage. A repeated interaction-family name need not identify a unique matrix cell. |
| Original-inventory reference | The imported description names a treatment destination or explicit related-discussion, see-also or specific-factor reference, with its relation semantics retained. | Importation into the SKB archive does not itself demonstrate SR-Site endorsement or full coverage. |
| SKB rationale without identifiable destination | An additional SKB discussion or assessment-basis explanation is present, but the preceding destination rules do not apply. | Additional text need not provide a destination or a scope-specific coverage explanation. |
| No identifiable documentary destination | None of the preceding documentary destination/explanation rules applies. | The record can still contain substantial imported text, causal relations, bibliographic references or named physical concepts. The label does not mean the phenomenon was substantively omitted. |

“SR-Site-stage” refers to the inspected archived assessment stage, not the present calendar date. “Earlier-stage” retains the stage named by the field or text. In the CSV schema, the compact `current_*` flags refer to SR-Site-stage evidence under this definition.

`documentary_unresolved=1` means no unique, existing destination can be resolved among the defined documentary associations at any inspected stage. A uniquely referenced PFEP counts as resolved even if that PFEP is also excluded. `no_resolved_relevant_destination=1` additionally excludes such non-relevant PFEP destinations; a resolved stage-qualified SKB destination qualifies without implying a current adoption decision. Neither flag is an estimate of substantive completeness. A resolvable see-also or related-discussion reference remains that relation type, not a proven coverage endpoint.

The provenance class and resolution flags are intentionally separate. For example, J 7.02 names earlier SAFE interaction families that have several matrix instances and therefore remains unresolved at the individual-record level. J 5.18 uniquely references J 4.2.05, but that destination is itself excluded. A 3.085 has ambiguous earlier SAFE families and separately resolvable original-inventory references.

## Identifier and relation rules

1. **Literal local identifiers.** Numeric references are resolved only within interpreted referential spans, using the source inventory's identifier namespace. Leading zeros are normalized by numeric component. Plain integer identifiers are supported. A number must be a whole token; a component embedded in a longer identifier cannot become an independent reference. Physical quantities, scientific notation, equation coefficients, numbered prose examples and report section numbers are not interpreted as PFEP identifiers merely because a similar catalogue number exists.
2. **Grammatical role.** A record described as covered by, treated in, split into, lumped into or replaced by another record is directed toward that destination. A number identifying another item to exclude is not a coverage endpoint. Incoming and outgoing causal references retain their actual direction and are not substituted for treatment assignments.
3. **Named references.** A name must occur in an interpreted referential statement. It is resolved within the stated source inventory, not against a global collection of similarly named FEPs. An expressly named factor-list section constrains the namespace. Without such a constraint, repeated names remain multiple candidates. Ordinary scientific terms are not expanded into foreign-inventory destinations. Title variants without an exact normalized match remain unresolved; similarity retrieval is a separate analysis.
4. **Structured process and variable fields.** Selected/list entries are split before whitespace is normalized. Exact names are qualified by the source's system component when supplied. Every compatible lookup result is retained; a name-only match never silently selects one duplicate. Unmatched names remain explicit unresolved references. Process/variable association is distinct from current-catalogue membership and affirmative coverage adoption.
5. **Assessment stage.** A field explicitly naming SR-Can is resolved against the SR-Can catalogue. The provisional `ProvBio` records are broad historical category records. They are neither nonexistent nor assumed to be SR-Site treatment records. SAFE matrix family names are checked in the SAFE table and their multiplicity is retained. An earlier dated reference to “processes below” without the corresponding versioned list is not linked by assumption to a later retained selection.
6. **Retained handling associations.** A live database edge is an association. An excluded source with retained edges receives an explicit status-conflict flag. In the full graph, `handled_flag`, `unhandled_flag` and `comment_flag` denote nonempty source fields; handled and unhandled text can coexist on the same edge. These markers do not measure complete substantive coverage.

## Reference and benchmark variables

`reference_verified=1` means the literal reference resolves unambiguously to an existing record and its stated grammatical direction is valid. It can describe a causal or contextual relation; it does not by itself mark a coverage destination.

`coverage_endpoint=1` marks the interpreted treatment, replacement, splitting, lumping, duplication or aspect-treatment relations listed in `STRICT_SEMANTICS`. A brief cross-reference used as the imported description in an administrative-rejection context is coded as a replacement cross-reference. “See also”, causes/effects and related-discussion-only references do not qualify. No endpoint label establishes that the destination covers every aspect of the source.

`benchmark_eligible=1` requires a PFEP endpoint, a valid direction, an unambiguous existing local destination, and a destination labelled Relevant in the SKB source population. Repeated occurrences of a source–target pair must be collapsed by the benchmark analysis. This constructs a benchmark of explicit original-inventory treatment references; it is not independent validation of SR-Site coverage. Excluded destinations and unresolved names remain in the provenance table with their actual statuses. Broad contextual references may be studied separately under their own declared scope.

`target_exists_in_stage` has values `yes`, `no` or `unknown`. `yes` reports lookup existence only. `no` means the literal ID/name was not resolved in the specified inspected lookup, not that the entity is nonexistent in all documents. `unknown` is used for unresolved original-programme report sections or unsupplied historical lists. `ambiguity` preserves repeated titles, historical family multiplicity and unresolved-reference conditions. An existing candidate is not necessarily the intended target.

At source level, `ambiguous_reference_present` specifically marks a reference with multiple matching records or matrix cells. `unresolved_reference_present` marks at least one `no` lookup result; `unverified_reference_present` marks at least one `unknown` result. `reference_resolution_issue_present` is their broader diagnostic union, including an unspecified historical list. These flags may overlap because a source can have several different kinds of reference.

## Coverage statements and adoption

`formal_reason_coverage_assertion=1` for every cohort member. The supplementary `skb_discussion_*` flags inspect the additional discussion, excluding that formulaic reason:

| Variable | Meaning |
|---|---|
| `skb_discussion_coverage_assertion_present` | The discussion attributes described source aspects to treatment elsewhere. |
| `skb_discussion_targeted_assertion_present` | Such a statement names a target/family or explicitly refers to a process list, even where the exact record or version cannot be resolved. |
| `skb_discussion_scope_rationale_present` | The discussion identifies which source aspects are assigned to, or left outside, treatment. This is a text-presence indicator, not a judgement that the explanation is sufficient. |
| `skb_adoption_documented` | A relation expressly attributes treatment to a named SKB assessment element or family. Its historical/current stage and any partial treatment remain explicit. |
| `current_skb_adoption_documented` | The inspected material expressly documents affirmative SR-Site-stage adoption of the identified relation as the basis of the current exclusion. Retained selections and earlier-stage statements alone do not qualify. |

Absence of an adoption flag is bounded by these archived fields. It does not establish that no rationale exists anywhere else in the safety case or the regulatory record.

## Reproduction and verification

Run `python code/extraction/build_covered_elsewhere_audit.py` from the package root to reconstruct `data/coverage_evidence_200.csv` and `data/provenance_relations.csv` from the declared snapshot and interpretations. Use `--raw-directory` to reconstruct directly from extracted original KSE files. To verify the complete official archive route, run `python code/extraction/validate_skb_archive.py /path/to/TR-10-45_FEP_database.zip`. The validation checks hashes, original fields, stage-qualified lookup tables, graph annotation flags and the resulting documentary outputs. It does not tune retrieval parameters or independently validate the supplied textual interpretations.

`python -m unittest discover -s code/extraction -p 'test_*.py'` checks the critical semantic boundaries: quantities versus identifiers, local integers, grammatical direction, title ambiguity, system-component qualification, historical stages, retained status conflicts, excluded target chains and literal-span round trips. Offsets are zero-based Python Unicode character indices in decoded source-field strings. Field hashes use their UTF-8 encoding; raw table hashes refer to the original KSE bytes.
