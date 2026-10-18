# Record and endpoint analysis

The analysis uses the fixed 200-record coverage cohort, its 55-record non-Project N stratum,
and the strict 18-source/42-pair retrieval benchmark. It is retrospective.

## Endpoint sets
For each configuration and k in {1, 5, 10, 20}, compute source hits, recovered pairs,
complete endpoint sets and mean per-source recall. Ineligible endpoints remain in the
denominator. Report the eight multi-endpoint sources separately.

## Source review tasks
Count distinct resolved (target type, identifier, assessment stage) triples for each
source. Zero targets assigns destination identification; one assigns single-destination
scope review; multiple assigns distributed-scope review. Historical association,
lookup qualification and retained-link status remain separate flags.

## Worked records
For I 165, compare the full target-pair set for I 126, I 058, I 061 and I 273 with the
handling graph. Preserve handled-aspect and comment-only rows separately. For H 1.6.3,
retain the ten enumerated source aspects and their exact Unicode character spans.

Source interpretations are research inputs. The tests check these transformations.
