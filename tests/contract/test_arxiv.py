import importlib
from datetime import datetime, timezone

import pytest

ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>https://arxiv.org/abs/2601.12345v2</id><title> Example\n Research </title><summary> Test abstract. </summary><published>2026-01-10T00:00:00Z</published><author><name>Researcher</name></author><link title="pdf" href="https://arxiv.org/pdf/2601.12345v2"/></entry></feed>'''


@pytest.mark.asyncio
async def test_arxiv_atom_contract_and_serial_request_spacing():
    try:
        m = importlib.import_module('researchflow.infrastructure.sources.arxiv')
        types = importlib.import_module('researchflow.ports.sources')
    except ModuleNotFoundError:
        pytest.fail('arxiv search not implemented')
    times = [0.0]
    sleeps = []
    class Fetcher:
        async def fetch(self, url):
            assert 'export.arxiv.org/api/query?' in url and 'max_results=8' in url
            return types.FetchedSource(url, url, ATOM, 'application/atom+xml', datetime.now(timezone.utc))
    async def sleep(n):
        sleeps.append(n)
        times[0] += n
    search = m.ArxivSearch(Fetcher(), clock=lambda: times[0], sleep=sleep)
    first = await search.search('evidence research')
    await search.search('other')
    assert first[0].title == 'Example Research' and first[0].authors == ('Researcher',)
    assert first[0].url == 'https://arxiv.org/pdf/2601.12345v2'
    assert sleeps == [3.0]


@pytest.mark.asyncio
async def test_malformed_xml_and_external_entities_rejected():
    try:
        m = importlib.import_module('researchflow.infrastructure.sources.arxiv')
    except ModuleNotFoundError:
        pytest.fail('arxiv search not implemented')
    with pytest.raises(ValueError, match='arxiv_protocol'):
        m.parse_atom(b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><feed>&e;</feed>')
