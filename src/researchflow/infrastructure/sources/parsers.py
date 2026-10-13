import asyncio
import io
import json
import sys

from bs4 import BeautifulSoup
from pypdf import PdfReader

from researchflow.domain.sources import SnapshotPage
from researchflow.ports.sources import ParsedDocument

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 200
PARSER_VERSION = 'canonical-pypdf-6-v1'


class DocumentParser:
    def parse(self, data: bytes, mime_type: str) -> ParsedDocument:
        if len(data) > MAX_BYTES:
            raise ValueError('too_large: source exceeds 20 MiB')
        if not data:
            raise ValueError('parse_failed: empty source')
        media = mime_type.partition(';')[0].strip().lower()
        title = ''
        try:
            if media == 'application/pdf':
                pdf = PdfReader(io.BytesIO(data), strict=True)
                if pdf.is_encrypted:
                    raise ValueError('parse_failed: encrypted PDF')
                if len(pdf.pages) > MAX_PAGES:
                    raise ValueError('too_many_pages: PDF exceeds 200 pages')
                pages = tuple(SnapshotPage(n + 1, p.extract_text() or '') for n, p in enumerate(pdf.pages))
                if not any(p.text.strip() for p in pages):
                    raise ValueError('unsupported_scan: PDF has no extractable text; OCR is not enabled')
                title = str(pdf.metadata.get('/Title','')) if pdf.metadata is not None else ''
            elif media in {'text/plain', 'text/markdown', 'text/x-markdown'}:
                pages = (SnapshotPage(1, data.decode('utf-8-sig', errors='strict')),)
            elif media == 'text/html':
                soup = BeautifulSoup(data.decode('utf-8-sig', errors='strict'), 'html.parser')
                title = soup.title.get_text(' ', strip=True) if soup.title else ''
                for node in soup(['script', 'style', 'noscript', 'template']):
                    node.decompose()
                pages = (SnapshotPage(1, soup.get_text('\n', strip=True)),)
            else:
                raise ValueError('unsupported_type: accept TXT, Markdown, HTML or text PDF')
        except ValueError as exc:
            if str(exc).startswith(('parse_failed', 'unsupported_', 'too_')):
                raise
            raise ValueError('parse_failed: source content cannot be decoded') from exc
        except Exception as exc:
            raise ValueError('parse_failed: invalid document') from exc
        if not any(p.text.strip() for p in pages):
            raise ValueError('parse_failed: document has no text')
        if sum(len(p.text.encode('utf-8')) for p in pages) > MAX_BYTES:
            raise ValueError('too_large: extracted text exceeds 20 MiB')
        return ParsedDocument(pages, PARSER_VERSION, title)

    async def parse_async(self, data: bytes, mime_type: str) -> ParsedDocument:
        if len(data) > MAX_BYTES:
            raise ValueError('too_large: source exceeds 20 MiB')
        if mime_type.partition(';')[0].strip().lower() != 'application/pdf':
            return self.parse(data, mime_type)
        # The owned child is terminated on cancellation. PDF CPU/memory cannot outlive the run.
        process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'researchflow.infrastructure.sources.pdf_worker', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            async with asyncio.timeout(30):
                stdout, _ = await process.communicate(data)
            if process.returncode != 0:
                raise ValueError('parse_failed: PDF parser resource limit or invalid content')
            result = json.loads(stdout)
            if 'error' in result:
                raise ValueError(result['error'])
            return ParsedDocument(tuple(SnapshotPage(p['number'], p['text']) for p in result['pages']), result['parser_version'], result['title'])
        except TimeoutError as exc:
            raise ValueError('parse_failed: PDF parser timed out') from exc
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
