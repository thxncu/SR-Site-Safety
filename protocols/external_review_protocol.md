# External-review evidence register and page retrieval frame

## Purpose and source boundaries

The register compares how three published reviews discuss FEP handling, documentary relationships and control of the SR-Site assessment evidence. The two SSM Technical Notes contain the conclusions of commissioned consultants in the initial review phase. The NEA report provides an international peer review. Their remits and access to SKB information differ. The sources therefore supply attributed observations and recommendations, rather than interchangeable measurements of the same outcome.

Source editions, download addresses and PDF hashes are identified in `external_review_sources.csv`. The page retrieval frame covers the English assessment text from the introduction to the final recommendations or conclusions in the two SSM reports, and from the high-level findings to the end of Chapter 4 in the NEA report. The exact printed ranges are SSM 2012:34, pp. 3–19; SSM 2012:36, pp. 3–43; and NEA 2012, pp. 9–135. Covers, contents, duplicated front-matter summaries, reference lists, lists of reviewed SKB reports, repeated recommendation appendices, biographies, terms of reference and reproduced guideline extracts lie outside these ranges. The chosen ranges include the original authors' report-level conclusions.

## Reproducible page retrieval

The physical PDF page is the retrieval unit. Text is extracted with `pdftotext -layout`, preserving form-feed page boundaries. The reported run used Poppler 24.02.0. The text is lowercased and alphabetic words broken by a hyphen at a line ending are joined. The regular expressions in `external_review_page_retrieval_specification.json` identify the following term families: FEP, traceability, database, document control, data control, qualification, quality assurance, cross-reference, mapping and screening. The search does not use critical or favorable wording as an eligibility filter.

The frame contains 185 physical pages, including one blank page. Eighty-three pages match one or more term families. Context is also required from SSM 2012:34 Section 3, pp. 18–19; SSM 2012:36, the end of Section 4.5 and Section 5, pp. 39–43; and NEA 2012, the high-level findings, pp. 10–11, and Sections 2.1–2.2.3, pp. 21–27. These sections state the reports' overall judgments and findings on presentation, assessment methods and completeness. Three NEA pages in the required context do not match the search terms: printed pp. 10, 21 and 26, corresponding to PDF pp. 12, 23 and 28. The combined retrieval frame contains 86 pages.

`external_review_page_frame.csv` records every physical page, its scope, matched term families, required-context status, text hash and links to selected passage IDs. All 42 selected passages have locators on 26 distinct pages within the 83 keyword-matching pages. Page retrieval supports inspection of the source context. A nonmatching page is not coded as substantively irrelevant, and 86 pages is not a denominator for the prevalence of documentary findings.

## Passage eligibility and selection

The analytical unit is a statement or qualified conclusion within one source section. An eligible statement meets at least one of the following criteria:

1. It identifies the source or destination of a FEP, data, model or supporting-argument relationship, or explains how a reader can recover that relationship.
2. It evaluates the reason, scope or applicability of an inclusion, exclusion, consolidation or data-selection decision.
3. It evaluates consistency, qualification, checking, responsibility or version propagation across assessment records.
4. It states a favorable judgment or a qualification needed to interpret one of these documentary issues, including a report-level conclusion about completeness, traceability or the significance of identified errors.

A passage is outside the analytical scope when it discusses only physical performance, experiments or dose consequences without a documentary relationship relevant to these criteria. Bibliographic entries, navigation text and repetitions introduced by translation are not analytical statements. An assertion without a recoverable source locator is not eligible. Direction alone cannot establish eligibility. A criticism and its explicit favorable or limiting qualification are retained together when they form one argument.

The register contains 42 purposively selected analytical statements. It is not an exhaustive extraction of all eligible statements from the retrieved pages. Its row-level `inclusion_rationale` and `scope_note` explain the choice and its relevant qualification. No total number of initially screened passages, rejected eligible passages, independent assessors or inter-coder agreement is inferred from the page counts. The page frame and the passage register use different units and are reported separately.

## Relationships and coding

Each row records the source edition, printed page, physical PDF page, source section, paraphrased finding, inclusion rationale, primary dimension, direction and related passage IDs. The paraphrase attributes the assessment to the source authors. The primary dimension follows the central documentary object, using `external_review_category_rules.csv`; it does not measure severity or regulatory significance. The direction is favorable, critical or mixed. Mixed statements preserve both the positive assessment or limiting qualification and the associated concern.

Summary recurrence is retained for contextual comparison and marked explicitly. R24 repeats the mapping-QA concern in R07, and R37 revisits the inconsistent Data Report role described in R25. R11 and R12 separate a questioned local exclusion from the source authors' conclusion that other inventory routes preserve catalogue coverage; they remain linked. Other related rows can discuss overlapping issues. Removing the two explicit summary recurrences would leave 40 selected statements, not 40 independent deficiencies.

## Source-level context and use

The register contains 24 statements from Hicks and Baldwin, 13 from Baldwin and Hicks, and five from the NEA review. Its 30 critical, eight mixed and four favorable labels describe the selection only. Interpretation also uses the reports' broader conclusions, recorded in `external_review_context_assessments.csv`. Hicks and Baldwin judge the iterative international checks to support broad FEP coverage and find included FEPs generally traceable. Baldwin and Hicks judge the errors they identified unlikely to affect the safety-case calculations or arguments, while recommending further checking. The NEA team considers SR-Site credible and adequate for the licensing step then under review and finds no major omissions, while recommending more reliable data and document control. These conclusions are part of the evidence, not a separate estimate of the frequency of favorable findings.

The analytical comparison identifies concrete review tasks: preserve the scope of a transferred process, identify the assessment use of a parameter, and propagate changed evidence to its dependent records. The source observations do not validate the retrieval benchmark or establish a causal effect of the present audit on historical safety calculations or licensing decisions.

## Reproduction

Obtain the three source PDFs listed in `external_review_sources.csv`, verify their hashes, and extract corresponding text files with `pdftotext -layout`. Use the stems `SSM_2012_34`, `SSM_2012_36` and `NEA_7084_2012`. Run `audit_selection_context.py --package PATH_TO_REPLICATION_PACKAGE --reports PATH_TO_SOURCE_PDF_AND_TXT_FILES --output PATH_TO_OUTPUT`. The script regenerates the page frame, source-level accounting, retrieval specification and Project N inventory-structure tables. Copyrighted report files are not redistributed with the replication data.
