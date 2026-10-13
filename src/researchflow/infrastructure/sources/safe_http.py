import asyncio
import ipaddress
import socket
import zlib
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

import httpcore
import httpx

from researchflow.ports.sources import FetchedSource, SourceAccessDeniedError

Resolver = Callable[[str], Awaitable[tuple[str, ...]]]
TransportFactory = Callable[[str, str], httpx.AsyncBaseTransport]


def public_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise SourceAccessDeniedError('invalid DNS address') from exc
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if not address.is_global or address.is_multicast:
        raise SourceAccessDeniedError('source address is not public')
    return str(address)


async def resolve_dns(host: str) -> tuple[str, ...]:
    results = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return tuple(dict.fromkeys(str(r[4][0]) for r in results))


class PinnedBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, ip: str, hostname: str) -> None:
        self.ip, self.hostname = public_ip(ip), hostname
        self.delegate = httpcore.AnyIOBackend()

    async def connect_tcp(self, host: str, port: int, timeout: float | None = None, local_address: str | None = None, socket_options=None):
        if host != self.hostname:
            raise SourceAccessDeniedError('connection hostname changed after validation')
        return await self.delegate.connect_tcp(self.ip, port, timeout=timeout, local_address=local_address, socket_options=socket_options)

    async def connect_unix_socket(self, *args, **kwargs):
        raise SourceAccessDeniedError('source fetching cannot use Unix sockets')

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class CoreStream(httpx.AsyncByteStream):
    def __init__(self, stream) -> None:
        self.stream = stream
    async def __aiter__(self):
        async for chunk in self.stream:
            yield chunk
    async def aclose(self) -> None:
        await self.stream.aclose()


class PinnedTransport(httpx.AsyncBaseTransport):
    def __init__(self, ip: str, hostname: str) -> None:
        self.hostname = hostname
        self.pool = httpcore.AsyncConnectionPool(network_backend=PinnedBackend(ip, hostname), max_connections=1, max_keepalive_connections=0, retries=0)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self.hostname:
            raise SourceAccessDeniedError('transport URL differs from pinned hostname')
        # Keeping the URL host preserves Host and certificate validation/SNI;
        # only connect_tcp receives the validated numeric IP.
        core_request = httpcore.Request(request.method, httpcore.URL(scheme=request.url.raw_scheme, host=request.url.raw_host, port=request.url.port, target=request.url.raw_path), headers=request.headers.raw, content=request.stream, extensions=request.extensions)
        response = await self.pool.handle_async_request(core_request)
        return httpx.Response(response.status, headers=response.headers, stream=CoreStream(response.stream), extensions=response.extensions)

    async def aclose(self) -> None:
        await self.pool.aclose()


class SourceFetcher:
    def __init__(self, resolver: Resolver = resolve_dns, transport_factory: TransportFactory = PinnedTransport, max_bytes: int = 20 * 1024 * 1024) -> None:
        if not 0 < max_bytes <= 20 * 1024 * 1024:
            raise ValueError('max_bytes must be within the source size limit')
        self.resolver, self.transport_factory, self.max_bytes = resolver, transport_factory, max_bytes

    async def target(self, value: str) -> tuple[httpx.URL, str]:
        if any(ord(c) < 32 for c in value):
            raise SourceAccessDeniedError('control characters in source URL')
        try:
            url = httpx.URL(value)
        except (ValueError, httpx.InvalidURL) as exc:
            raise SourceAccessDeniedError('invalid source URL') from exc
        if url.scheme not in {'http', 'https'} or not url.host or url.userinfo:
            raise SourceAccessDeniedError('only public HTTP(S) URLs without credentials are allowed')
        host = url.host.lower().rstrip('.')
        if host == 'localhost' or host.endswith(('.localhost', '.local')):
            raise SourceAccessDeniedError('local hostname is prohibited')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            async with asyncio.timeout(5):
                addresses = await self.resolver(host)
            if not addresses:
                raise SourceAccessDeniedError('source hostname has no address')
            validated = tuple(public_ip(a) for a in addresses)
            ip = validated[0]
        else:
            ip = public_ip(host)
        return url.copy_with(fragment=None), ip

    async def fetch(self, url: str) -> FetchedSource:
        original, current = url, url
        async with asyncio.timeout(60):
            for redirect in range(6):
                target, ip = await self.target(current)
                async with httpx.AsyncClient(transport=self.transport_factory(ip, target.host), trust_env=False, follow_redirects=False, timeout=httpx.Timeout(30, connect=5, pool=5), headers={'User-Agent': 'ResearchFlow/1.0 (research source reader)', 'Accept-Encoding': 'gzip, identity'}) as client:
                    async with client.stream('GET', target) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            if redirect == 5:
                                raise ValueError('redirect_limit: source redirects exceed five')
                            location = response.headers.get('location')
                            if not location:
                                raise ValueError('source_protocol: redirect has no location')
                            current = str(target.join(location))
                            continue
                        response.raise_for_status()
                        declared = response.headers.get('content-length')
                        if declared and (not declared.isdecimal() or int(declared) > self.max_bytes):
                            raise ValueError('too_large: declared source size is invalid or exceeds limit')
                        encoding = response.headers.get('content-encoding', 'identity').lower().strip()
                        if encoding not in {'identity', 'gzip'}:
                            raise ValueError('source_protocol: unsupported content encoding')
                        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == 'gzip' else None
                        output, raw_size = bytearray(), 0
                        try:
                            async for chunk in response.aiter_raw(chunk_size=65536):
                                raw_size += len(chunk)
                                if raw_size > self.max_bytes:
                                    raise ValueError('too_large: compressed source exceeds limit')
                                part = decoder.decompress(chunk, self.max_bytes - len(output) + 1) if decoder else chunk
                                output.extend(part)
                                if len(output) > self.max_bytes:
                                    raise ValueError('too_large: decompressed source exceeds limit')
                            if decoder:
                                if not decoder.eof:
                                    raise ValueError('source_protocol: truncated gzip source')
                                if decoder.unused_data:
                                    raise ValueError('source_protocol: trailing gzip data')
                        except zlib.error as exc:
                            raise ValueError('source_protocol: invalid gzip source') from exc
                        media = response.headers.get('content-type', 'application/octet-stream').partition(';')[0].lower().strip()
                        return FetchedSource(original, str(target), bytes(output), media, datetime.now(timezone.utc))
        raise ValueError('redirect_limit')
