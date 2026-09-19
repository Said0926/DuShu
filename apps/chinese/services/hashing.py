"""Stable cache keys for pieces of chinese text."""

import hashlib


def sentence_hash(sentence: str) -> str:
    """Return the cache key for a sentence.

    Hashing rather than indexing the text itself: sentences can be long, and a
    64-character key indexes far better than an unbounded string.

    The sentence is stripped first so that the same sentence pasted with
    different surrounding whitespace hits the same cache entry.

    This lives in ``chinese`` rather than next to one of the caches because both
    ``translation`` and ``tts`` key their caches by sentence. They are sibling
    infrastructure apps, so importing from one into the other would break the
    rule that dependencies point one way only.
    """
    return hashlib.sha256(sentence.strip().encode("utf-8")).hexdigest()
