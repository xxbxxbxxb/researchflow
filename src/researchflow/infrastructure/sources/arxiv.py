import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from urllib.parse import urlencode

from defusedxml import ElementTree

from researchflow.ports.sources import FetcherPort, SourceCandidate

ATOM = '{http://www.w3.org/2005/Atom}'


def parse_atom(data: bytes) -> tuple[SourceCandidate, ...]:
    try:
        root = ElementTree.fromstring(data)
        if root.tag != ATOM + 'feed':
            raise ValueError('not an Atom feed')
        candidates = []
        for entry in root.findall(ATOM + 'entry'):
            def content(name: str) -> str:
                return ' '.join((entry.findtext(ATOM + name) or '').split())
            source_id, title = content('id'), content('title')
            if not source_id or not title or source_id.endswith('/errors'):
                raise ValueError('missing arxiv fields or error response')
            links = entry.findall(ATOM + 'link')
            url = next((link.attrib['href'] for link in links if link.attrib.get('title') == 'pdf'), source_id)
            published = datetime.fromisoformat(content('published').replace('Z', '+00:00'))
            if published.tzinfo is None:
                raise ValueError('arxiv timestamp must have timezone')
            authors = tuple((author.findtext(ATOM + 'name') or '').strip() for author in entry.findall(ATOM + 'author'))
            candidates.append(SourceCandidate(source_id, title, url, content('summary'), authors, published))
        return tuple(candidates)
    except Exception as exc:
        raise ValueError('arxiv_protocol: invalid Atom response') from exc


class ArxivSearch:
    def __init__(self, fetcher: FetcherPort, clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.fetcher, self.clock, self.sleep = fetcher, clock, sleep
        self.lock = asyncio.Lock()
        self.last_request: float | None = None

    async def search(self, query: str, limit: int = 8) -> tuple[SourceCandidate, ...]:
        if not query.strip() or len(query) > 5000 or not 1 <= limit <= 8:
            raise ValueError('invalid arxiv search query or limit')
        params = urlencode({'search_query': 'all:' + query, 'start': 0, 'max_results': limit, 'sortBy': 'relevance'})
        async with self.lock:
            if self.last_request is not None:
                delay = max(0.0, 3.0 - (self.clock() - self.last_request))
                if delay:
                    await self.sleep(delay)
            self.last_request = self.clock()
            fetched = await self.fetcher.fetch('https://export.arxiv.org/api/query?' + params)
        return parse_atom(fetched.data)[:limit]
