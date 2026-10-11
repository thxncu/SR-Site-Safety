"""Deterministic auxiliary retrieval for archived FEP records.

Retrieval scores are analytical similarities. They neither classify documentary
provenance nor establish a coverage relationship. Candidate eligibility is
applied before ranking, and missing source text is represented explicitly.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


BASELINE_WEIGHTS = (0.35, 0.25, 0.25, 0.15)
SOURCE_FIELDS = (
    "pfep_description", "pfep_comments", "comments_needs_discussion",
    "assessment_basis_comment",
)
CANDIDATE_FIELDS = ("pfep_name", "pfep_description", "pfep_comments")
WORD_OPTIONS = dict(stop_words="english", ngram_range=(1, 2), max_features=30000)
CHAR_OPTIONS = dict(analyzer="char_wb", ngram_range=(3, 5), max_features=40000)


def clean(value):
    if value is None or (not isinstance(value, (str, list, tuple, set, dict)) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def norm(value):
    value = unicodedata.normalize("NFKD", clean(value)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def ifeps(value):
    """Read stored taxonomy identifiers; do not infer references from prose."""
    return {part for part in re.split(r"[;,\s]+", clean(value))
            if re.fullmatch(r"\d+(?:\.\d+)+", part)}


def split_ids(value):
    return {part.strip() for part in clean(value).split(";") if part.strip()}


def normalized_indel_similarity(a, b):
    """Exact normalized Indel similarity, 2 LCS / combined string length."""
    length = len(a) + len(b)
    if not length:
        return 1.0
    masks = {}
    for index, symbol in enumerate(b):
        masks[symbol] = masks.get(symbol, 0) | (1 << index)
    state = 0
    for symbol in a:
        x = masks.get(symbol, 0) | state
        state = x & ~(x - ((state << 1) | 1))
    return 2.0 * state.bit_count() / length


def _text(frame, fields):
    values = []
    for field in fields:
        if field not in frame:
            raise ValueError(f"Required text field is absent: {field}")
        values.append(frame[field].map(clean))
    return pd.concat(values, axis=1).agg(" ".join, axis=1).map(clean)


def _vectors(vectorizer, corpus, n_source, fallback_titles, empty_source):
    """Fit once; title fallback transforms only queries in the same space."""
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError as error:
        if "empty vocabulary" not in str(error):
            raise
        zeros = np.zeros((n_source, len(corpus) - n_source), dtype=float)
        return zeros, zeros.copy(), np.zeros(n_source, dtype=int), 0
    query = matrix[:n_source]
    targets = matrix[n_source:]
    baseline = cosine_similarity(query, targets)
    fallback = baseline.copy()
    selected = np.flatnonzero(empty_source)
    if len(selected):
        transformed = vectorizer.transform([fallback_titles[i] for i in selected])
        fallback[selected] = cosine_similarity(transformed, targets)
    return baseline, fallback, np.diff(query.indptr), len(vectorizer.vocabulary_)


@dataclass
class RetrievalComponents:
    source: pd.DataFrame
    relevant: pd.DataFrame
    source_text: pd.Series
    candidate_text: pd.Series
    word: np.ndarray
    character: np.ndarray
    title: np.ndarray
    shared_ifep: np.ndarray
    fallback_word: np.ndarray
    fallback_character: np.ndarray
    word_nonzero_features: np.ndarray
    character_nonzero_features: np.ndarray
    vocabulary_sizes: dict

    @property
    def source_text_empty(self):
        return self.source_text.eq("").to_numpy()

    def model_scores(self):
        baseline = score(self.word, self.character, self.title, self.shared_ifep)
        # Dropping terms without renormalisation preserves their contribution
        # scale. For an empty source vector this ablation equals the baseline.
        title_only = score(self.word, self.character, self.title, self.shared_ifep,
                           (0.0, 0.0, 0.25, 0.15))
        fallback = score(self.fallback_word, self.fallback_character,
                         self.title, self.shared_ifep)
        return {
            "baseline_text_fields": baseline,
            "title_only_ablation": title_only,
            "missing_text_title_fallback": fallback,
        }


def load_population(data):
    data = Path(data)
    population = pd.read_csv(data / "pfep_relevance_population_1671.csv",
                             dtype=str, keep_default_na=False)
    excluded = pd.read_csv(data / "not_relevant_370_normalized.csv",
                           dtype=str, keep_default_na=False)
    for frame in (population, excluded):
        if not frame.pfep_id.is_unique:
            raise ValueError("PFEP identifiers must be unique within each input table")
    relevant = population[population.relevance.map(clean).str.lower().eq("relevant")].reset_index(drop=True)
    source = excluded[pd.to_numeric(excluded.covered_by_other_feps_flag).eq(1)].reset_index(drop=True)
    if not set(source.pfep_id).issubset(set(population.pfep_id)):
        raise ValueError("The covered-elsewhere source set is outside the population")
    return population, source, relevant


def build_components(source, relevant):
    source = source.reset_index(drop=True).copy()
    relevant = relevant.reset_index(drop=True).copy()
    source_text = _text(source, SOURCE_FIELDS)
    candidate_text = _text(relevant, CANDIDATE_FIELDS)
    corpus = source_text.tolist() + candidate_text.tolist()
    source_titles = source.pfep_name.map(clean).tolist()
    empty = source_text.eq("").to_numpy()
    W, WF, Wn, Wv = _vectors(TfidfVectorizer(**WORD_OPTIONS), corpus, len(source), source_titles, empty)
    C, CF, Cn, Cv = _vectors(TfidfVectorizer(**CHAR_OPTIONS), corpus, len(source), source_titles, empty)
    source_names = source.pfep_name.map(norm).tolist()
    target_names = relevant.pfep_name.map(norm).tolist()
    # A missing title is missing evidence rather than an exact-match signal.
    T = np.array([[normalized_indel_similarity(a, b) if a and b else 0.0
                   for b in target_names] for a in source_names], dtype=float)
    source_sets = source.international_fep_numbers_all.map(ifeps)
    target_sets = relevant.international_fep_numbers_all.map(ifeps)
    F = np.array([[len(a & b) for b in target_sets] for a in source_sets], dtype=int)
    return RetrievalComponents(source, relevant, source_text, candidate_text,
                               W, C, T, F, WF, CF, Wn, Cn,
                               {"word": Wv, "character": Cv})


def components(data):
    """Compatibility interface returning the unmodified text-field components."""
    _, source, relevant = load_population(data)
    result = build_components(source, relevant)
    return source, relevant, result.word, result.character, result.title, result.shared_ifep


def score(W, C, T, F, weights=BASELINE_WEIGHTS):
    return weights[0] * W + weights[1] * C + weights[2] * T + weights[3] * (F > 0)


def rank_candidates(scores, shared, identifiers, excluded=(), require_shared=True):
    """Apply eligibility before sorting; resolve exact ties by PFEP identifier."""
    excluded = set(excluded)
    eligible = [j for j, identifier in enumerate(identifiers)
                if identifier not in excluded and (not require_shared or shared[j] > 0)]
    return sorted(eligible, key=lambda j: (-float(scores[j]), identifiers[j]))


def conditional_outcome(order, scores, threshold):
    if not order:
        return "no_eligible_candidate"
    if float(scores[order[0]]) < threshold:
        return "best_eligible_below_threshold"
    return "candidate_at_or_above_threshold"


def benchmark_rank(order, identifiers, gold_targets):
    positions = {identifiers[j]: rank for rank, j in enumerate(order, 1)}
    eligible = {target: positions[target] for target in gold_targets if target in positions}
    return (min(eligible.values()) if eligible else None), eligible
