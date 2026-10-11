# Manuscript and analysis crosswalk

Manuscript: **Traceability of screening decisions for features, events and processes in Sweden's SR-Site safety case**. Package version 2.1.0, 10 October 2026.

Paths are relative to the package root. Data filenames without a directory prefix refer to `data/`. The abbreviation FEP denotes feature, event or process; PFEP denotes project FEP; IFEP denotes International FEP. SKB denotes the Swedish Nuclear Fuel and Waste Management Company. Source evidence, auxiliary search results and proposed checks have distinct analytical roles.

## Main manuscript

| Element | Principal data | Reproduction or interpretation |
|---|---|---|
| **Table 1: sources and populations** | `pfep_relevance_population_1671.csv`; `not_relevant_370_normalized.csv`; `coverage_evidence_200.csv`; `pfep_srsite_network_edges.csv`; `external_review_findings_42.csv` | `code/compute_core_results.py` calculates population counts. The review register uses selected passage units. |
| **Table 2: documentary sources and resolution in 55 non-Project N records** | `non_project_n_census_55.csv`; `non_project_n_summary.json`; `non_project_n_inventory_summary.csv`; `provenance_relations.csv` | `code/compute_cohort_and_retrieval_checks.py`. Classes contain 10, 9, 18, 3 and 15 records; 10, 8, 18, 0 and 0 have a resolvable association at any inspected layer. |
| **Table 3: endpoint recovery under alternative retrieval rules** | `retrieval_main_table_seven_rows.csv`; `retrieval_rank_comparison_summary.csv`; `retrieval_rank_comparison_cases.csv`; `retrieval_rank_comparison_pairs.csv` | The same census/comparison script calculates all 24 configurations. The seven selected rows report endpoint recovery, with all 18 sources retained. |
| **Table 4: technical assessment tasks in two worked routes** | `technical_route_evidence.json`; `technical_case_handling_rows.json`; `worked_documentary_paths.csv`; `provenance_relations.csv` | Source-linked interpretation of H 1.6.3 and I 165. Report locators, receiving processes, premises and transfer checks are explicit. No radionuclide calculation is performed by the package. |
| **Table 5: proposed record checks, roles and triggers** | `documentary_implementation_checks.csv`; `specifications/`; `code/record_checks/` | Six record checks distinguish evidence fields, application consistency and remaining technical judgment. The schema and local checker propose an implementation contract. |
| **Figure 1: FEP levels and documentary relationships** | Inventory profiles, population and catalogue definitions, documentary classes and provenance | `code/draw_figure1.py`; separates inventory entries, taxonomy and receiving safety-case associations. |
| **Figure 2: documentary routes and technical dependencies** | H 1.6.3 and I 165 in worked-case, relation and technical-route files | `code/draw_figure2.py --output-dir figures`; an engineering-context diagram with source-grounded directions and distinct assessment transfer checks. |

## Supplementary Material sections

Section labels S1 through S8 are distinct from table numbers S1 through S12.

| Section | Files and methods | Interpretation boundary |
|---|---|---|
| **S1.1: screening phrases** | `phrase_codebook_23.csv`; `not_relevant_370_normalized.csv` | The 23 exact cleaned reasons identify the asserted screening operation. |
| **S1.2: inventory and population** | Population tables; `leave_one_project_out_sensitivity.csv`; `inventory_relevance_association.csv`; `inventory_relevance_chi2_cells.csv`; `project_n_inventory_structure.csv` | Ordinary and bias-corrected Cramér's V describe inventory-by-relevance association. Numeric parenthood and a formal heading reason are different variables. |
| **S1.3: source profiles** | `source_inventory_profiles_10.csv`; `non_project_n_inventory_summary.csv`; `non_n_heading_coverage_records.csv` | The 55-record stratum combines different source scopes and includes 20 formal headings. Project K has zero coverage records. |
| **S2: fields and extraction** | Dictionary, source manifest, decoded source snapshot, interpretation rules and extraction code | Field locators and literal spans expose the declared interpretations and examined editions. |
| **S3: documentary provenance** | `coverage_evidence_200.csv`; `provenance_relations.csv`; documentary class/property summaries; `non_project_n_*` outputs | Origin, stage, meaning, resolution and adoption are separate properties. The 19-record follow-up table preserves source text and proposed checks. |
| **S4: auxiliary retrieval** | `retrieval_*`; `lookup_candidate_*`; `code/semantic/`; rank-comparison protocol | The imported endpoint set has 18 sources and 42 unique pairs. Ranking and candidate eligibility are reported separately. The numeric mask preserves named semantic references. |
| **S5: cases** | `process_tracing_cases.csv`; `process_tracing_steps.csv`; `worked_documentary_paths.csv`; both technical JSON files; path protocol | Thirteen purposive cases with 49 inspection steps and two technical routes. Neither case frequency nor inspection steps estimate prevalence or reviewer time. |
| **S6: network and handling** | `pfep_srsite_network_edges.csv`; `srsite_catalogue_407.csv`; `srsite_fep_network_metrics.csv`; `handling_annotation_patterns.csv` | Full and finally relevant association scopes remain distinct. Handled and unhandled-aspect annotations can coexist. |
| **S7: external reviews** | `external_review_*`; review protocol; `code/audit_selection_context.py` | The 256-page index, 185-page assessment frame, 86 retrieval/context pages and 42 selected passages use distinct units. Report-level context and summary recurrence are supplied. |
| **S8: archived continuity** | `database_release_comparison_2014.csv`; optional `code/continuity/compare_2014_release.py`; source manifest | Archived full-population and fixed-200 comparisons. A different assessment context does not establish continuity in the current preliminary safety analysis report (PSAR) database. |

## Supplementary tables and figure

| Element | Section | Data and analytical role |
|---|---|---|
| **Table S1: screening phrases** | S1 | `phrase_codebook_23.csv`; all 23 cleaned reasons. |
| **Table S2: population and inventory omission** | S1 | Population and leave-one-inventory outputs; `inventory_relevance_association.csv` gives both effect-size forms. |
| **Table S3: inventory profiles** | S1 | `source_inventory_profiles_10.csv`; context for the ten screened inventories. |
| **Table S4: fields and extraction** | S2 | `DATA_DICTIONARY.csv`; snapshot, extraction protocol and source manifest. |
| **Table S5: documentary provenance** | S3 | `coverage_evidence_200.csv`; `provenance_relations.csv`; class/property summaries and non-Project N census. |
| **Table S6: field availability and search outcomes** | S4 | `retrieval_field_missingness.csv`; `retrieval_search_outcomes.csv`; separate field and eligibility conditions. |
| **Table S7: threshold comparisons** | S4 | `retrieval_threshold_sensitivity.csv`; fixed documentary cohorts and empty-pool outcomes. |
| **Table S8: all 18 strict endpoint cases** | S4 | `retrieval_benchmark_cases.csv`; `retrieval_benchmark_source_evidence.csv`; full source/pair comparisons and identifier audit in Data S3. |
| **Table S9: 13 worked paths** | S5 | `worked_documentary_paths.csv`; case and step registers. |
| **Table S10: handling annotations** | S6 | `handling_annotation_patterns.csv`; handled-aspect and non-handling fields kept distinct. |
| **Table S11: external-review categories** | S7 | Category rules, composition and selected-passage register; context and selection-accounting tables in Data S5. |
| **Figure S1: review-page frame** | S7 | `external_review_selection_accounting.csv`; `code/draw_selection_frame.py --accounting data/external_review_selection_accounting.csv --output figures`. |
| **Table S12: archived continuity** | S8 | `database_release_comparison_2014.csv`; archived population and fixed-cohort results. |

## Supplementary Data groups

| Designation | Machine-readable contents |
|---|---|
| **Data S1: population and context** | `pfep_relevance_population_1671.csv`; `not_relevant_370_normalized.csv`; `phrase_codebook_23.csv`; `source_inventory_profiles_10.csv`; `project_n_inventory_structure.csv`; `project_n_inventory_structure_summary.json`; `non_n_heading_coverage_records.csv`; `inventory_relevance_association.csv`; `inventory_relevance_chi2_cells.csv`; `pfep_srsite_network_edges.csv`; `srsite_catalogue_407.csv`; `srsite_fep_network_metrics.csv`; `handling_annotation_patterns.csv`; `leave_one_project_out_sensitivity.csv`; `database_release_comparison_2014.csv`. |
| **Data S2: documentary evidence** | `coverage_evidence_200.csv`; `provenance_relations.csv`; `documentary_class_distribution.csv`; `documentary_properties.csv`; `non_project_n_census_55.csv`; `non_project_n_unresolved_records_19.csv`; `non_project_n_inventory_summary.csv`; `non_project_n_domain_summary.csv`; `non_project_n_reason_by_class.csv`; `non_project_n_summary.json`; decoded source snapshot and interpretation rules. |
| **Data S3: retrieval and lookups** | `retrieval_source_text_availability.csv`; `retrieval_field_missingness.csv`; `retrieval_search_outcomes.csv`; `retrieval_candidate_rankings.csv`; `retrieval_benchmark_source_evidence.csv`; `retrieval_benchmark_cases.csv`; `retrieval_benchmark_summary.csv`; `retrieval_model_comparison.csv`; `retrieval_threshold_sensitivity.csv`; `retrieval_weight_sensitivity.csv`; `lookup_candidate_relations.csv`; `lookup_candidate_summary.csv`; `retrieval_benchmark_verified_occurrences_44.csv`; `retrieval_benchmark_unique_pairs_42.csv`; `retrieval_benchmark_query_texts.csv`; `retrieval_identifier_mask_audit.csv`; `retrieval_rank_comparison_cases.csv`; `retrieval_rank_comparison_pairs.csv`; `retrieval_rank_comparison_top20.csv`; `retrieval_rank_comparison_summary.csv`; `retrieval_main_table_seven_rows.csv`; retrieval specification/summary JSON files. |
| **Data S4: paths and proposed checks** | `process_tracing_cases.csv`; `process_tracing_steps.csv`; `worked_documentary_paths.csv`; `documentary_implementation_checks.csv`; `technical_route_evidence.json`; `technical_case_handling_rows.json`; `specifications/screening_record.schema.json`; `specifications/observed_H_1_6_3.json`; `specifications/review_interface.openapi.json`; local checker in `code/record_checks/`. |
| **Data S5: external reviews** | `external_review_findings_42.csv`; `external_review_sources.csv`; `external_review_category_rules.csv`; `external_review_composition.csv`; `external_review_context_assessments.csv`; `external_review_page_frame.csv`; `external_review_selection_accounting.csv`; `external_review_page_retrieval_specification.json`; `external_review_input_manifest.csv`. |

`analysis_summary.json` consolidates core calculated results. `cohort_retrieval_input_hashes.json` and `cohort_retrieval_files_manifest.csv` identify shared inputs and derived files for Data S2 and S3. `references.json` contains bibliography metadata. The notebook calls `code/reproduce_analysis.py` and maintains no separate analysis implementation.

## Variables requiring particular care

| Variable | Meaning |
|---|---|
| `documentary_class` | Priority class describing an observed documentary source layer, assigned without similarity retrieval. |
| `documentary_unresolved` | No unique existing destination is resolvable through the defined association types at any inspected stage. An excluded PFEP target can count as resolved. |
| `no_resolved_relevant_destination` | Alternative condition requiring a finally relevant PFEP destination or a destination in its stage-qualified non-PFEP catalogue. |
| `formal_heading_only` / `recorded_heading_only_coverage_reason` | Recorded screening reason. It is distinct from `is_numeric_parent`, which describes identifier structure. |
| `stored_ifep_domains` | Grouping derived from stored taxonomy identifiers. Domains can overlap; they are not a new safety-function or risk classification. |
| `reference_verified` | An unambiguous existing reference with valid direction; its meaning can be contextual or causal. |
| `coverage_endpoint` | A reference with the declared treatment/replacement meaning, without an assertion of complete coverage. |
| `current_*` | SR-Site-stage evidence in the inspected archive, not present-day operating status. |
| `handled_flag` / `unhandled_flag` | Presence of a handled-aspect or non-handling-reason field. Both can occur on one association. |
| `search_outcome` | A result conditional on eligibility, fields, score and threshold, separate from documentary class. |
| `hit_at_k` | At least one source-verified endpoint within the first k candidates. It does not measure precision. |
| `verified_endpoint_recall_at_k` | Fraction of the declared endpoint set recovered within k. Source averages and pooled pair denominators are separate outputs. |
| `endpoint_rank` | Full rank within the eligible candidate population; blank when the verified endpoint is ineligible. |
| `identifier_masked_query` | Query with audited numeric reference tokens removed; substantive endpoint names and titles remain. |
| `normalized_exact_title` / `same_inventory_identifier_descendant` | Analytical lookup methods producing search leads. |
| `benchmark_scope` | Strict treatment endpoints versus broader directional references. |
| `source_record_id` | Physical record number local to the named source table. |
| `span_start` / `span_end` | Zero-based, end-exclusive Unicode offsets in a decoded source field. |
| `pdf_page_1based` | Physical PDF page number, distinct from a report's printed page label. |
| `retrieved_page_or_context` | Page selected by the declared term rules or mandatory report-level context rule. |
| `selected_register_passages` | Selected passage identifiers whose reported source locations include the page; one passage can span several pages. |

The page frame is reconstructed only when official report files are supplied through `--reports`; default reproduction uses the provided frame and accounting. Review classifications, technical-route interpretations and proposed checks are declared inputs with exposed sources and rationales.
