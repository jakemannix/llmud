"""Fuzzy matching for lore lookups."""

from difflib import SequenceMatcher
from typing import List


def find_similar(query: str, candidates: List[str], max_results: int = 3) -> List[str]:
    """
    Find similar strings to a query from a list of candidates.

    Uses SequenceMatcher to compute similarity ratios and returns
    the most similar candidates, sorted by similarity.

    Args:
        query: The search query
        candidates: List of possible matches
        max_results: Maximum number of suggestions to return

    Returns:
        List of similar strings, sorted by similarity (most similar first)
    """
    if not candidates:
        return []

    query_lower = query.lower()

    # Calculate similarity scores for each candidate
    scored = []
    for candidate in candidates:
        candidate_lower = candidate.lower()

        # Check for substring match first (higher priority)
        if query_lower in candidate_lower or candidate_lower in query_lower:
            score = 0.9  # High score for substring matches
        else:
            # Use SequenceMatcher for fuzzy matching
            score = SequenceMatcher(None, query_lower, candidate_lower).ratio()

        scored.append((candidate, score))

    # Sort by score descending and filter out very low scores
    scored.sort(key=lambda x: x[1], reverse=True)

    # Return top results with score > 0.3
    results = [
        candidate for candidate, score in scored[:max_results]
        if score > 0.3
    ]

    return results
