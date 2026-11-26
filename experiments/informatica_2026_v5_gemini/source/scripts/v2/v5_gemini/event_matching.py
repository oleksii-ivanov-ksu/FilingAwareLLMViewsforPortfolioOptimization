"""Matching of model events to manually annotated events.

A model event matches an annotated event when their texts are similar enough: the larger of
the token-set ratio of the two descriptions and the partial ratio of the two quotes
(rapidfuzz), with a threshold of 60 out of 100. Matching is greedy, best pair first, and
every event is matched at most once. Event-type labels are not compared.
"""
from rapidfuzz import fuzz

from src.extraction.grounding import normalize

MATCH_THRESHOLD = 60.0


def event_sim(a, b):
    da, db = normalize(a.get('description', '')), normalize(b.get('description', ''))
    qa, qb = normalize(a.get('source_quote', '')), normalize(b.get('source_quote', ''))
    return max(fuzz.token_set_ratio(da, db) if da and db else 0, fuzz.partial_ratio(qa, qb) if qa and qb else 0)


def match_events(model_events, gold_events, threshold=MATCH_THRESHOLD):
    """Return the matched pairs as (model index, annotated index, score)."""
    pairs = sorted(((event_sim(m, g), i, j) for i, m in enumerate(model_events) for j, g in enumerate(gold_events)), reverse=True)
    used_m, used_g, matched = set(), set(), []
    for score, i, j in pairs:
        if score >= threshold and i not in used_m and j not in used_g:
            used_m.add(i); used_g.add(j); matched.append((i, j, score))
    return matched
