"""What a whole map is made of.

Provenance is an honesty guarantee, not decoration: it is what stops a generated
map being mistaken for a survey, and it is on screen for the same reason it is
in the exported file. Each source declares its own; a map made of several needs
one word for the lot.

The rule is that **a map is only as trustworthy as its least trustworthy layer**.
Adding one synthetic layer to a measured map does not leave a measured map.
"""

from __future__ import annotations

from typing import Iterable

from hipparchus.application.source_stack import default_sources

#: Weakest first. The order is by how far the value sits from direct
#: observation: a model, then something generated, then something observed but
#: not in physical units, then the two kinds of direct observation.
#:
#: `live` and `measured` are both direct observation and sit together at the
#: strong end. `live` is placed first so that a map mixing surveyed and
#: instrument data reports "live" — the commonest such map is a street map with
#: contours on it, and "live" is the word the OpenStreetMap row already shows,
#: so the badge and the source list agree.
RANKING: tuple[str, ...] = (
    "approximate",
    "synthetic",
    "uncalibrated",
    "live",
    "measured",
)


def weakest(values: Iterable[str]) -> str | None:
    """The least trustworthy claim in the set, or ``None`` if there is none.

    An unranked kind — one a plugin invented — is treated as weaker than
    anything known, so a new source cannot quietly promote a map.
    """
    known = list(values)
    if not known:
        return None
    return min(known, key=lambda value: (_rank(value), value))


def _rank(value: str) -> int:
    try:
        return RANKING.index(value) + 1
    except ValueError:
        return 0


#: The same thing, named for what it does at the call site.
merged = weakest


def for_sources(source_ids: Iterable[str]) -> str | None:
    """One word for a map built from these sources.

    Sources not in the stack are ignored rather than counted as unknown: they
    are ids that no longer exist, not sources with an unfamiliar claim.
    """
    declared = {
        definition.source_id: definition.provenance for definition in default_sources()
    }
    found = [declared[source_id] for source_id in source_ids if source_id in declared]
    return weakest(found)
