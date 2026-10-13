import importlib
import io
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def parser():
    try:
        return importlib.import_module('researchflow.infrastructure.sources.parsers').DocumentParser()
    except ModuleNotFoundError:
        pytest.fail('document parser not implemented')


def pdf_bytes(pages=2, text=True):
    writer = PdfWriter()
    for n in range(pages):
        page = writer.add_blank_page(width=200, height=200)
        if text:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 10 100 Td (Page {n+1} experiment) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_canonical_chinese_text_and_html_blocks():
    p = parser()
    document = p.parse('中文实验\r\ne\u0301'.encode(), 'text/markdown')
    assert document.pages[0].text == '中文实验\né'
    html = p.parse(b'<title>Research</title><style>hidden</style><h1>Heading</h1><p>Useful</p><script>evil()</script>', 'text/html')
    assert html.title == 'Research'
    assert 'Useful' in html.pages[0].text
    assert 'hidden' not in html.pages[0].text and 'evil' not in html.pages[0].text


def test_physical_pdf_pages_are_preserved():
    document = parser().parse(pdf_bytes(), 'application/pdf')
    assert [(p.number, p.text.strip()) for p in document.pages] == [(1, 'Page 1 experiment'), (2, 'Page 2 experiment')]


@pytest.mark.asyncio
async def test_chinese_pdf_owned_parser_and_saved_quote_offsets():
    from datetime import datetime, timezone

    from researchflow.application.evidence import anchor_evidence, validate_anchor
    from researchflow.domain.sources import SourceSnapshot
    data = (Path(__file__).parents[1] / 'fixtures/sources/chinese-two-pages.pdf').read_bytes()
    document = await parser().parse_async(data, 'application/pdf')
    assert document.pages[1].number == 2 and '第二页保留物理页码' in document.pages[1].text
    snapshot = SourceSnapshot('s', 'p', 'upload:chinese.pdf', 'hash', document.pages, document.parser_version, datetime.now(timezone.utc))
    quote = '中文实验样本为十二个'
    start = snapshot.pages[0].text.index(quote)
    evidence = anchor_evidence(snapshot, 1, start, start + len(quote))
    validate_anchor(evidence, snapshot)
    assert snapshot.pages[0].text[evidence.anchor.start:evidence.anchor.end] == quote


@pytest.mark.parametrize('data,mime,error', [(b'', 'text/plain', 'parse_failed'), (b'\xff', 'text/plain', 'parse_failed'), (b'bad pdf', 'application/pdf', 'parse_failed'), (b'x' * (20 * 1024 * 1024 + 1), 'text/plain', 'too_large'), (b'hello', 'application/octet-stream', 'unsupported_type')], ids=['empty', 'bad-utf8', 'bad-pdf', 'oversize', 'unknown-type'])
def test_rejects_invalid_and_oversize_sources(data, mime, error):
    with pytest.raises(ValueError, match=error):
        parser().parse(data, mime)


def test_scans_and_too_many_pages_are_explicit():
    p = parser()
    with pytest.raises(ValueError, match='unsupported_scan'):
        p.parse(pdf_bytes(text=False), 'application/pdf')
    with pytest.raises(ValueError, match='too_many_pages'):
        p.parse(pdf_bytes(201, text=False), 'application/pdf')


@pytest.mark.asyncio
async def test_prepared_source_has_safe_blob_and_no_visible_side_effect(tmp_path):
    try:
        module = importlib.import_module('researchflow.application.ingestion')
        types = importlib.import_module('researchflow.ports.sources')
    except ModuleNotFoundError:
        pytest.fail('ingestion not implemented')
    from researchflow.infrastructure.storage.blob_store import BlobStore
    class Repository:
        calls = 0
        async def save_snapshot(self, snapshot, title=None):
            self.calls += 1
            return snapshot
    repository = Repository()
    blob = BlobStore(tmp_path / 'blobs')
    service = module.IngestSource(repository, blob, parser())
    source = types.SourceInput(filename='../../outside', data='实验'.encode(), media_type='text/plain')
    prepared = await service.prepare('p', source)
    assert repository.calls == 0 and blob.get(prepared.blob_key) == '实验'.encode()
    assert not (tmp_path / 'outside').exists()
    saved = await service.execute('p', source)
    assert saved.pages[0].text == '实验' and repository.calls == 1
