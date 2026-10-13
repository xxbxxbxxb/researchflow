import gzip
import importlib

import httpx
import pytest


def module():
    try:
        return importlib.import_module('researchflow.infrastructure.sources.safe_http')
    except ModuleNotFoundError:
        pytest.fail('safe source fetch not implemented')


class RawStream(httpx.AsyncByteStream):
    def __init__(self, content):
        self.content = content
    async def __aiter__(self):
        for n in range(0, len(self.content), 4096):
            yield self.content[n:n+4096]


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['http://127.0.0.1/x', 'http://localhost/x', 'http://169.254.169.254/latest', 'http://10.0.0.1/', 'http://[::ffff:127.0.0.1]/', 'file:///etc/passwd', 'https://user:pass@example.org/'])
async def test_prohibited_targets_never_create_transport(url):
    m = module()
    calls = []
    async def resolve(host):
        return ('127.0.0.1',)
    def transport(ip, host):
        calls.append(ip)
        return httpx.MockTransport(lambda request: httpx.Response(200, content=b'no'))
    fetcher = m.SourceFetcher(resolver=resolve, transport_factory=transport)
    with pytest.raises(m.SourceAccessDeniedError):
        await fetcher.fetch(url)
    assert calls == []


@pytest.mark.asyncio
async def test_redirect_revalidates_dns_and_blocks_private_hop():
    m = module()
    calls = []
    async def resolve(host):
        return ('93.184.216.34',) if host == 'example.org' else ('10.0.0.2',)
    def transport(ip, host):
        calls.append((ip, host))
        return httpx.MockTransport(lambda request: httpx.Response(302, headers={'location': 'https://private.test/secret'}))
    with pytest.raises(m.SourceAccessDeniedError):
        await m.SourceFetcher(resolver=resolve, transport_factory=transport).fetch('https://example.org/')
    assert calls == [('93.184.216.34', 'example.org')]


@pytest.mark.asyncio
async def test_actual_connection_uses_pinned_ip_and_original_tls_name():
    m = module()
    backend = m.PinnedBackend('93.184.216.34', 'example.org')
    class Network:
        async def connect_tcp(self, host, port, **kwargs):
            assert host == '93.184.216.34' and port == 443
            return 'connected'
    backend.delegate = Network()
    assert await backend.connect_tcp('example.org', 443) == 'connected'
    with pytest.raises(m.SourceAccessDeniedError):
        await backend.connect_tcp('changed.test', 443)
    transport = m.PinnedTransport('93.184.216.34', 'example.org')
    class Pool:
        async def handle_async_request(self, request):
            assert request.url.host == b'example.org'  # core derives TLS SNI from this, not the IP
            assert (b'Host', b'example.org') in request.headers
            import httpcore
            return httpcore.Response(200, content=RawStream(b'ok'))
    transport.pool = Pool()
    response = await transport.handle_async_request(httpx.Request('GET', 'https://example.org'))
    assert await response.aread() == b'ok'


@pytest.mark.asyncio
async def test_dns_is_resolved_once_then_only_numeric_target_passed_to_transport():
    m = module()
    count = 0
    async def resolve(host):
        nonlocal count
        count += 1
        return ('93.184.216.34',) if count == 1 else ('127.0.0.1',)
    def transport(ip, host):
        assert ip == '93.184.216.34' and host == 'example.org'
        return httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-type': 'text/plain'}, stream=RawStream('实验'.encode())))
    result = await m.SourceFetcher(resolver=resolve, transport_factory=transport).fetch('https://example.org/')
    assert count == 1 and result.data == '实验'.encode()


@pytest.mark.asyncio
async def test_gzip_bomb_is_bounded_during_decompression():
    m = module()
    async def resolve(host):
        return ('93.184.216.34',)
    content = gzip.compress(b'x' * 100_000)
    def transport(ip, host):
        return httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-encoding': 'gzip'}, stream=RawStream(content)))
    with pytest.raises(ValueError, match='too_large'):
        await m.SourceFetcher(resolver=resolve, transport_factory=transport, max_bytes=1024).fetch('https://example.org/')


@pytest.mark.asyncio
async def test_mixed_public_private_dns_never_connects():
    m = module()
    async def resolve(host):
        return ('93.184.216.34', '127.0.0.1')
    def transport(ip, host):
        pytest.fail('mixed DNS set must be rejected before connection')
    with pytest.raises(m.SourceAccessDeniedError):
        await m.SourceFetcher(resolver=resolve, transport_factory=transport).fetch('https://example.org/')


@pytest.mark.asyncio
async def test_valid_gzip_and_raw_limit_are_enforced():
    m = module()
    async def resolve(host):
        return ('93.184.216.34',)
    def valid(ip, host):
        return httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-encoding': 'gzip', 'content-type': 'text/plain'}, stream=RawStream(gzip.compress('研究'.encode()))))
    assert (await m.SourceFetcher(resolver=resolve, transport_factory=valid).fetch('https://example.org/')).data == '研究'.encode()
    def large(ip, host):
        return httpx.MockTransport(lambda request: httpx.Response(200, stream=RawStream(b'x' * 1025)))
    with pytest.raises(ValueError, match='too_large'):
        await m.SourceFetcher(resolver=resolve, transport_factory=large, max_bytes=1024).fetch('https://example.org/')


@pytest.mark.asyncio
async def test_redirect_limit_and_gzip_completion():
    m = module()
    async def resolve(host):
        return ('93.184.216.34',)
    def loop(ip, host):
        return httpx.MockTransport(lambda request: httpx.Response(302, headers={'location': '/next'}))
    with pytest.raises(ValueError, match='redirect_limit'):
        await m.SourceFetcher(resolver=resolve, transport_factory=loop).fetch('https://example.org/')
    def broken(ip, host):
        return httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-encoding': 'gzip'}, stream=RawStream(gzip.compress(b'text')[:-4])))
    with pytest.raises(ValueError, match='truncated'):
        await m.SourceFetcher(resolver=resolve, transport_factory=broken).fetch('https://example.org/')
