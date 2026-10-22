"""Keyword-search provider interface.

Some platforms (e.g. Stardima) cannot resolve an IMDb ID directly —
they expose their own search endpoint and scoped identifiers. Such
scrapers subclass :class:`KeywordProvider` and implement ``search``.

Keyword providers are discovered automatically (see :mod:`discovery`);
the registry aggregates their ``search`` results alongside IMDb
suggestions and deduplicates by ``imdb_id``.

Synthetic IDs
-------------
A keyword source may have no IMDb mapping for a match. Its ``imdb_id``
then uses the form ``{scheme}:{ref}`` (e.g. ``stardima:12345``), which
the ``imdb_id`` field pattern in :class:`SearchResult` accepts. These
IDs are scoped by ``scheme`` so results from different sources never
collide.

When such a title is chosen, the provider's ``resolve`` receives its own
synthetic ID and must map it back to a playable stream.
"""

from __future__ import annotations

import abc

from ..models import MediaType, SearchResult
from .base import BaseProvider


class KeywordProvider(BaseProvider, abc.ABC):
    """Base class for sources that search raw keywords, not IMDb IDs.

    Subclasses must define a unique ``scheme`` (used to namespace
    synthetic IDs) and implement ``search``.
    """

    scheme: str = "kw"

    @abc.abstractmethod
    def search(
        self,
        query: str,
        media_type: MediaType | None = None,
    ) -> list[SearchResult]:
        """Return matches for a raw keyword query.

        ``imdb_id`` values may be synthetic IDs produced by
        :meth:`synthetic_id` when the platform has no IMDb mapping.
        """

    @classmethod
    def synthetic_id(cls, ref: str) -> str:
        """Namespace a platform reference into a valid synthetic ID."""
        return f"{cls.scheme}:{ref}"

    @classmethod
    def ref_from_id(cls, imdb_id: str) -> str | None:
        """Extract the platform reference from a synthetic ID.

        Returns ``None`` when the ID does not belong to this provider's
        scheme (e.g. a real IMDb ``tt...`` ID).
        """
        prefix = f"{cls.scheme}:"
        if imdb_id.startswith(prefix):
            return imdb_id[len(prefix) :]
        return None
