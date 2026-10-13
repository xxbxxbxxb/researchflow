import json
import sys
from dataclasses import asdict


def main() -> None:
    if sys.platform != 'win32':
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    from researchflow.infrastructure.sources.parsers import DocumentParser, MAX_BYTES
    try:
        result = asdict(DocumentParser().parse(sys.stdin.buffer.read(MAX_BYTES + 1), 'application/pdf'))
    except ValueError as exc:
        result = {'error': str(exc)}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
