# Auxiliary retrieval: rank-comparison protocol

## Purpose and endpoints

A feature, event or process is abbreviated FEP; a project FEP is abbreviated PFEP. The auxiliary search locates records for source inspection. A retrieved candidate does not create an archived documentary relation. The rank comparison evaluates recovery of source-qualified imported references: 18 query records, 42 unique source-endpoint pairs and 44 provenance occurrences. Every endpoint is a PFEP classified Relevant in the archived population. No Project N record or empty-text query belongs to this endpoint set.

The endpoint set is not a complete set of relevance judgments. A candidate outside the endpoint set can be a useful follow-up record. A recovered endpoint can address only part of a source, and its presence does not establish adoption as the basis of the SR-Site screening decision.

## Text and vectorizer control

Queries concatenate four archived fields: imported description, imported comments, Swedish Nuclear Fuel and Waste Management Company (SKB) discussion and SKB assessment-basis comment. Candidate text concatenates title, imported description and imported comments. The source title is a separate similarity component. The candidate universe is fixed at 1,301 relevant PFEPs.

Word term frequency-inverse document frequency (TF-IDF) uses English stop words, unigrams and bigrams, and at most 30,000 features. Character TF-IDF uses within-word 3-to-5-grams and at most 40,000 features. Each vectorizer is fitted once on the same unmasked joint corpus of 200 source texts and 1,301 candidate texts. Both unmasked and masked queries use the fixed vocabulary, inverse document frequencies and candidate vectors. Title similarity is twice the longest common subsequence length divided by the combined length of the normalized titles. Exact ties are resolved by ascending PFEP identifier.

## Models and eligibility

Six score specifications are evaluated: the fixed reference weighted score; the same content coefficients after removing the International FEP (IFEP) bonus and renormalizing; equal word, character and title weights; word TF-IDF alone; character TF-IDF alone; and title similarity alone. Each model is evaluated both with and without a shared-IFEP eligibility requirement. The fixed reference weighted score retains its IFEP indicator term in the ungated comparison; the content-only version separates that bonus from the effect of candidate eligibility.

The fixed coefficients 0.35, 0.25, 0.25 and 0.15 and the 0.34 lead flag are fixed heuristics. No objective function, optimization procedure or held-out validation set selected these parameters in the reported analysis. The rank comparison does not tune them and does not use the 0.34 threshold. The numerical effect of an empty query follows directly from the formula and is a representation diagnostic.

## Numeric-identifier sensitivity

The mask removes only numeric or fully qualified PFEP identifier literals inside source-verified PFEP-reference evidence spans. It replaces each token with whitespace. The procedure uses the audited target literal and source field to restrict removal. It does not remove numeric strings outside reference spans, avoiding accidental deletion of physical quantities, times and report numbers. A deletion audit records each relation, source field, token, position and evidence span.

The mask removes 31 numeric-reference tokens from 15 of the 18 benchmark queries. Three A-inventory queries use named references and remain unchanged. Source titles and substantive endpoint names remain in every query. Candidate text and taxonomy metadata remain fixed. The sensitivity check therefore measures dependence on explicit numeric identifiers; it does not provide a leakage-free or independently held-out test.

## Metrics

For each model, query variant and eligibility rule, the outputs report every verified endpoint rank and the best verified endpoint rank for each source. An ineligible endpoint has no rank. Hit@k is one when at least one verified endpoint occurs within rank k. Mean reciprocal rank assigns zero to a source with no eligible endpoint. Endpoint recall is also reported at k, with both source-averaged and pair-aggregated denominators. These endpoint measures do not estimate precision because relevance judgments are incomplete.

The shared-IFEP gate leaves 19 of 42 verified endpoint pairs eligible and preserves at least one endpoint for 16 of 18 sources. Ungated comparisons retain all 42 endpoint pairs. The code reports both counts so that a ranking score cannot hide the eligibility ceiling.

## Reproduction and scope

The same executable used for the cohort census generates all 24 configurations, 432 source/configuration rows, 1,008 endpoint/configuration rows and the top 20 eligible candidates per configuration. The specification file records score coefficients, software versions and masking details. The case-level outputs retain each verified endpoint rank and its eligibility status. The masking audit identifies every removed numeric reference, while the source and candidate texts preserve the technical context needed to interpret each retrieval result.

The comparison is limited to the implemented lexical components. No dense-embedding model results are reported. The choice of a transparent locator permits inspection of why a record was returned; the documentary relation is established by examining its source and decision context. A model evaluated on a different scientific-language task cannot establish that relation from a similarity score.
