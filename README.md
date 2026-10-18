# SR-Site FEP coverage records and retrieval analysis

Version 3.3.0. Accompanies *Traceability of Inherited FEP Coverage Decisions for Geological Disposal Safety Assessment Updates*.

## Data and scope

The package contains source-derived records, explicit interpretation rules and executable analyses of the public SR-Site FEP archive. The screened population contains 1,671 PFEPs, including 370 exclusions and 200 coverage exclusions. The principal cohort contains 55 records outside Project N. The 145 generic Project N exclusions form a separate stratum.

The analysis follows a retrospective, single-analyst documentary design. Raw wording, interpretation rules and calculated results are separate inputs and outputs. Source evidence includes file and field hashes, record identifiers, literal spans, relation direction, namespace, assessment stage and lookup outcomes. Relation selection describes documented identity and treatment assignments. Technical coverage is assessed separately from those recorded relationships.

## Run the calculations

Python 3.13.5 and the package versions in `requirements.txt` specify the execution environment. From this directory:

```bash
python -m pip install -r requirements.txt
python code/reproduce.py --skip-figures
```

Omit `--skip-figures` to regenerate figures as well. The command runs the base archive analysis, source-level tasks and endpoint metrics, BM25 and resampling comparisons, and relation-rule sensitivity. Output files are written to `data/`. Figure scripts write to `figures/`.

The calculations use the accompanying extracted records. Original runtime archives and report files remain at the official locations in `source_manifest.csv`. The source-comparison procedures under `code/extraction/` describe how to check extracted fields against those files. Such a comparison requires the original downloads and the conversion dependencies specified by the relevant procedure.

## Data groups

- **Data S1:** screened populations, reason codebook, source profiles, Project N hierarchy, handling graph and historical release comparison.
- **Data S2:** the 200-source coverage table, 55-source principal census, literal relation evidence, interpretation rules, lookup results, source-level tasks and relation-rule sensitivity.
- **Data S3:** query texts, numerical mask spans, candidate rankings, 28 search configurations, endpoint metrics and composition sensitivity.
- **Data S4:** 13 worked cases, 49 documentary steps, technical report locations, source-level tasks, ten thermal aspects, four I 165 branches, six record checks and the record schema.
- **Data S5:** the 42-passage external-review register, selection rules, report-level context and page index.

`DATA_DICTIONARY.csv`, `RECORD_DATA_DICTIONARY.csv` and `RELATION_RULE_DATA_DICTIONARY.csv` describe fields. Protocols are stored in `protocols/` and beside the relevant extraction code. The supplementary material gives the corresponding analytical methods and table definitions.

## Locate the article results

The article develops a record-level procedure for reviewing inherited coverage decisions before assessment reuse. The record analysis, retrieval benchmark and worked cases supply complementary evidence for that procedure.

| Article location | Supporting material |
| --- | --- |
| Table I; supplementary Table S21 | Comparisons with the cited traceability, FEP-review, database and integration studies; the manuscript gives the references. |
| Table II | Population, inventory and handling-graph data in Data S1. |
| Tables III–IV; Section IV.A | `data/non_project_n_census_55.csv`, `data/record_review_queue_55.csv` and the relation evidence in Data S2. |
| Table V | `data/record_endpoint_metrics_24_configs.csv`, BM25 and composition-sensitivity results in Data S3. |
| Table VI | `data/record_I165_branch_inventory.csv` and the complete source-located handling rows in Data S4. |
| Table VII | The six record checks and the record schema in Data S4. |
| Supplementary Table S22 | `data/relation_rule_sensitivity_summary.csv` and `data/relation_rule_sensitivity_sources.csv`. |

## Endpoint metrics and sensitivity

The strict retrieval benchmark contains 18 sources and 42 distinct documented source-endpoint pairs. All configurations retain these denominators. Hit@k counts sources with at least one recovered endpoint. Pair recall counts recovered endpoint pairs. Source-averaged recall gives each source equal weight. Complete-set recovery counts sources for which every documented endpoint appears within the first k candidates.

The 24 lexical configurations cross six scoring rules, two masking conditions and two candidate-eligibility conditions. Four BM25 configurations cross the same masking and eligibility conditions. Source-cluster resampling uses 10,000 paired draws and the PCG64 seed 20261017. Source and inventory omission retain fixed candidate ranks and change the summarized query population.

Relation-rule sensitivity reuses the same recorded interpretations and lookups for all 55 sources:

- **R1:** the principal identity rule retains uniquely resolved, direction-valid associations in the declared semantic classes.
- **R2:** R1 with a relevant PFEP destination or a stage-qualified SKB target.
- **R3:** R2 with contextual `see_also`, `related_discussion` and `specific_factor_reference` relations removed.

The rules resolve 36, 35 and 33 sources. These are nested selection results, not estimates of independent coding agreement. `data/relation_rule_sensitivity_sources.csv` contains all 165 source-rule results; `data/relation_rule_sensitivity_summary.csv` contains their totals.

## Software tests

The software tests check parsing, fixed calculations, record structure and the responses to deliberately constructed fault conditions. Synthetic records in `tests/synthetic_fixtures/` are distinguishable from observed source records.

```bash
python -m unittest discover -s code/extraction -p 'test_*.py'
python -m unittest discover -s code/semantic -p 'test_*.py'
python -m unittest discover -s code/record_checks -p 'test_*.py'
python -m unittest discover -s code -p 'test_record_analysis.py'
python -m unittest discover -s code -p 'test_retrieval_robustness.py'
python -m unittest discover -s code -p 'test_relation_sensitivity.py'
python code/test_cohort_retrieval_checks.py --package . --output data
```

These tests establish computational behavior under specified inputs. They do not supply independent interpretation of the archival text or validation of repository performance.

## File integrity and citation

`SHA256SUMS.txt` records file hashes. On systems with `sha256sum`, run `sha256sum -c SHA256SUMS.txt` from this directory. Cite the accompanying study and identify version 3.3.0; `CITATION.cff` supplies citation metadata. Original source attribution and literal wording are retained in the research data.
