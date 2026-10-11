# Replication package

## Traceability of screening decisions for features, events and processes in Sweden's SR-Site safety case

Package version **2.1.0**, dated **10 October 2026**, accompanying the manuscript.

The package examines all **1,671 project feature, event or process (PFEP) records** screened in the archived SR-Site table: 1,301 relevant records and 370 exclusions from ten inventories. Of the exclusions, 200 assert coverage elsewhere. The principal detailed cohort comprises all **55 coverage records outside Project N**. Their source text, formal reasons, associations and proposed record checks are supplied at record level. Project N is evaluated separately because its generic inventory structure dominates the full-cohort destination and missing-text counts.

Feature, event or process is abbreviated FEP; International FEP is abbreviated IFEP. SKB denotes the Swedish Nuclear Fuel and Waste Management Company. NEA denotes the Nuclear Energy Agency of the Organisation for Economic Co-operation and Development (OECD). SSM denotes the Swedish Radiation Safety Authority. SR-Site, SR-Can, SAFE and SR-PSU are assessment labels present in the records. An SR-Site-stage association identifies an archived assessment context.

## Run the analysis

The core workflow uses Python 3.12 and the pinned dependencies in `requirements.txt`. From the package root:

```sh
python -m pip install -r requirements.txt
python code/reproduce_analysis.py
```

The command reconstructs documentary evidence from the supplied source snapshot and interpretation rules, computes auxiliary retrieval and aggregate results, builds the 55-record census and 24 retrieval comparisons, calculates inventory-structure summaries, checks the proposed record example and generates **Figures 1, 2 and S1**. Outputs are written to `data/` and `figures/`. The default workflow uses the supplied review-page accounting for Figure S1. It requires no official report download and performs no separate archive conversion.

To rebuild the optional page retrieval frame, provide a directory containing the official reports and the matching text files described in `protocols/external_review_protocol.md`:

```sh
python code/reproduce_analysis.py --reports /path/to/official_review_reports
```

Required filename stems are `SSM_2012_34`, `SSM_2012_36` and `NEA_7084_2012`, each with `.pdf` and `.txt` extensions. Text must be extracted with `pdftotext -layout`. The optional route checks the report hashes, reconstructs page-level inclusion and retrieval flags, and regenerates the selection accounting before drawing Figure S1. It preserves the declared 42-passage register; it does not reclassify passages automatically.

`notebooks/replication_analysis.ipynb` calls the same workflow and displays the outputs. A Jupyter environment is optional. Computational tests can be run separately:

```sh
python -m unittest discover -s code/extraction -p 'test_*.py'
python -m unittest discover -s code/semantic -p 'test_*.py'
python code/test_cohort_retrieval_checks.py --package . --output data
python -m unittest discover -s code/record_checks -p 'test_*.py'
```

## Package organization

| Location or group | Contents |
|---|---|
| **Data S1: population and context** | Screened population, exclusion reasons, ten inventory profiles, Project N identifier structure, non-Project N heading records, inventory-by-relevance association, network annotations and archived 2014 comparison. |
| **Data S2: documentary evidence** | All 200 coverage records, provenance relations, class and resolution summaries, the complete 55-record census, its 19 unresolved records and inventory/domain summaries. |
| **Data S3: auxiliary retrieval** | Source-field availability, candidates, source-verified endpoints, all 24 ranking configurations, numeric-identifier masking audit, threshold and weight comparisons, specifications and input/output manifest. |
| **Data S4: worked paths and proposed checks** | Thirteen cases, 49 inspection steps, two engineering routes, verbatim handling rows and six implementation checks. The proposed record contract is in `specifications/`. |
| **Data S5: external reviews** | The 42-passage register, source and category information, report-level assessment context, 256-page frame, three-source selection accounting and report/text input manifest. |
| `code/` | Reproduction workflow, documentary extraction, lexical retrieval, census and ranking comparisons, selection-frame accounting, record checks, figures and optional archive readers. |
| `protocols/` | Census, rank comparison, worked-path selection and external-review selection protocols. |
| `DATA_DICTIONARY.csv` | Definitions, data types, blank-value meanings and derivations for every supplied CSV column. |
| `MANUSCRIPT_ANALYSIS_CROSSWALK.md` | Manuscript and supplementary table/figure mappings, file groups and interpretation notes. |

All data-group filenames are listed in the crosswalk. Scientific interpretation inputs, extracted source values and computed outputs have distinct roles. The default workflow reads the supplied inventory profiles, reference interpretations, worked-case selections and review classifications as declared inputs.

## The 55-record cohort and Project N

The non-Project N cohort comprises A 10, E 1, H 2, I 2, J 24, M 11, S 1 and W 4. Project K has no coverage-elsewhere record and remains a zero-coverage row in the inventory summary. These sources include project/concept inventories, the repository-type encyclopedia E and project/site inventories S and W. They contain 20 formal heading-only exclusions and 35 general-entry exclusions. All 55 have nonempty query text, but text availability does not measure engineering detail.

| Documentary class | Records outside Project N | Records with a resolvable association at any inspected layer |
|---|---:|---:|
| SR-Site-stage SKB association | 10 | 10 |
| Earlier-stage SKB association | 9 | 8 |
| Original-inventory reference | 18 | 18 |
| SKB rationale without identifiable destination | 3 | 0 |
| No identifiable documentary destination | 15 | 0 |
| **Total** | **55** | **36** |

Class and resolution are separate properties. A lower-priority imported relation can resolve a source whose selected SKB variable remains ambiguous. The 19 unresolved records comprise 15 without an identifiable destination, three with an explanatory rationale and one historical matrix ambiguity. `non_project_n_unresolved_records_19.csv` supplies each source and a proposed follow-up check. The alternative criterion requiring a finally relevant PFEP or a resolved SKB destination at a specified assessment stage leaves 20 records unresolved because J 5.18 points to excluded J 4.2.05. E SFL-00 is an umbrella entry referring to 57 inventory entries; it is counted once.

Project N contributes 145 coverage records, all with the formal reason “Heading only, covered by other NEA project FEPs.” Of these, 144 have empty imported descriptions and comments. Numeric identifier structure marks only 15 as parents and 130 as leaves. A formal heading disposition therefore cannot be reduced to numeric parenthood. The bias-corrected Cramér's V for inventory and relevance is 0.586 for the full population and 0.150 outside Project N. These statistics describe inventory composition; they do not establish a causal inventory effect. The underlying contingency tables and cell contributions are supplied.

The complete 200-record audit retains Project N transparently: 36 records have a resolvable association and 164 do not under the declared rules. The non-Project N analysis and the documented aggregation levels determine how those full-cohort counts should be interpreted. A heading can be represented by a documented child set or aggregate disposition rather than an artificial one-to-one physical-process link. See `protocols/non_project_n_cohort_protocol.md` and `code/extraction/documentary_protocol.md`.

## Auxiliary retrieval and rank comparison

Retrieval proposes records for inspection; it does not add archived relations. Queries concatenate imported description, imported comments, SKB discussion and assessment-basis comments. Candidate text concatenates title, imported description and imported comments. The source title supplies a separate similarity component. Candidates are fixed at all 1,301 relevant PFEPs.

The fixed score combines word term frequency-inverse document frequency (TF-IDF) cosine similarity, character TF-IDF cosine similarity, normalized title similarity and a shared-IFEP indicator with coefficients 0.35, 0.25, 0.25 and 0.15. The 0.34 cutoff is a heuristic lead flag. No optimization objective or independent validation set selected those values. Word settings use English stop words, unigrams/bigrams and at most 30,000 features; character settings use within-word three- to five-grams and at most 40,000 features. Vectorizers are fitted once on the unmasked joint corpus of 200 source texts and 1,301 candidate texts. Title similarity is twice the longest common subsequence length divided by the combined normalized title length.

The comparison uses six score specifications: `archived_weighted_score`, `weighted_content_only`, `equal_content_weights`, `word_tfidf_only`, `character_tfidf_only` and `title_similarity_only`. Each is evaluated with unmasked and identifier-masked queries, both with and without a shared-IFEP eligibility gate, yielding **24 configurations**. Ties are resolved by ascending PFEP identifier. Ranking comparisons do not use the 0.34 cutoff. Parameters are recorded in `retrieval_rank_comparison_specification.json` and the executable code.

The strict reference set contains 18 source queries, 42 unique source-endpoint pairs and 44 provenance occurrences. These are recoverable imported treatment or replacement references. All 18 sources remain in every denominator. The shared-IFEP gate retains 19 of the 42 endpoints and at least one endpoint for 16 sources. Hit@k records whether any verified endpoint is among the first k candidates; it is not a precision estimate. Source and endpoint ranks, mean reciprocal rank and endpoint recall are supplied for every configuration.

The seven configurations in manuscript Table 3 are provided in `retrieval_main_table_seven_rows.csv`. The fixed gated score recovers an endpoint for 10, 13 and 15 of 18 sources at ranks 1, 5 and 10. The numeric-identifier mask removes 31 reference tokens in 15 source queries within audited evidence spans. It preserves substantive endpoint names, source titles, physical quantities and candidate texts. The masked gated score gives the same three hit counts. The sensitivity check assesses dependence on explicit identifiers; it is not a held-out test of undocumented coverage. None of the 18 sources belongs to Project N or has an empty query.

The full rank outputs contain 432 source/configuration rows and 1,008 endpoint/configuration rows. Separate top-20 lists expose the leading candidates and component scores. The supplied component comparisons support a transparent secondary locator. No dense-embedding experiment is reported. Field-ablation, missing-text fallback, threshold and weight outputs provide additional diagnostics with their model identifiers preserved. See `protocols/auxiliary_retrieval_comparison_protocol.md`.

## External-review selection and technical paths

The review register contains 42 purposively selected passages: 24 from SSM 2012:34, 13 from SSM 2012:36 and five from OECD/NEA 2012. The reproducible page frame covers 256 physical pages, of which 185 fall in the specified English assessment sections. Keyword retrieval identifies 83 pages; three additional report-level context pages produce 86 retrieval/context pages. The selected passages occur on 26 distinct pages. Page counts and passage counts use different units. The frame documents where passages were sought; it is not an exhaustive count of all eligible passages.

The selected register has 30 critical, eight mixed and four favorable entries. The separate report-context table preserves the reviews' overall assessments and qualifications. Two explicit summary recurrences are identified, so the 42 entries do not represent 42 independent findings. These purposive selections cannot establish the prevalence of criticism across the complete reports. SSM Technical Notes state the named consultants' conclusions and need to be attributed accordingly. Full inclusion, exclusion, context and recurrence rules are in `protocols/external_review_protocol.md`.

The 13 worked cases and their 49 steps expose different reference origins, historical ambiguities, applicability reasons and search conditions. Two cases connect these records to technical assessment tasks: H 1.6.3 to Bu13 impurity alteration and the bounded buffer-chemistry route; I 165 through separate imported endpoints to buffer colloid loss and iron-copper corrosion. `technical_route_evidence.json` supplies report editions, page/section locators, engineering premises and the specific transfer checks. `technical_case_handling_rows.json` preserves the handling-table wording. These routes examine the scope that a reviewer needs to follow; they do not calculate a new radionuclide release or attribute a licensing outcome to a database field.

`specifications/record_contract.md` explains the proposed versioned schema, interface and local checks. Screening authority, relation adoption, source aggregation and receiving component are separate fields. JSON format errors, application consistency issues and remaining technical review tasks are reported separately. The H 1.6.3 example preserves the three named screening authorities and the Buffer receiving context while leaving unspecified source component and relation scope visible. No integration with an existing digital safety-case program is asserted.

## Official sources and archived continuity

Original archives and reports are not redistributed. `source_manifest.csv`, `external_review_input_manifest.csv` and source metadata identify official locations and hashes. The following optional commands require the separately obtained official sources:

```sh
python code/extraction/validate_skb_archive.py /path/to/TR-10-45_FEP_database.zip
python code/continuity/compare_2014_release.py /path/to/SKB_2014_FEP_database.zip /path/to/fmp2sqlite
```

The first command checks archive identity, normalized records, the snapshot, target lookups, graph annotations and resulting documentary outputs. It does not independently adjudicate textual interpretations. Direct reconstruction from extracted KSE tables is available with `python code/extraction/build_covered_elsewhere_audit.py --raw-directory /path/to/KSE_tables`. Separately supplied NEA metadata and cross-copy provenance fields remain declared inputs.

The optional 2014 converter is supplied by [fmptools](https://github.com/evanmiller/fmptools), used at commit `27387196484386691f311c00b5727dcbe5ee4cb3`. Its build requires a C compiler and SQLite development files. The comparison uses the full population, all 370 exclusions, association sets and the fixed 200-record coverage cohort. It finds unchanged screening status, assessed reason/note fields and association sets, with one revision-date change. SR-PSU separately classifies 199 of the 200 records as not relevant and retains coverage wording for 197. Those observations concern an archived release and a different assessment. They do not reproduce the current preliminary safety analysis report (PSAR) database.

## Integrity and citation

`CITATION.cff` contains citation metadata and `data/references.json` contains the scholarly bibliography. `cohort_retrieval_input_hashes.json` and `cohort_retrieval_files_manifest.csv` identify the census and ranking inputs and outputs. Package-file checksums can be checked from the root:

```sh
sha256sum -c SHA256SUMS.txt
```

Scientific source hashes identify the examined editions; package-file checksums identify supplied files. Regenerating outputs under another software environment can change byte-level representations.
