"""Bounded diagnostics and actual browser images from synthetic CI fixtures."""
import base64
from pathlib import Path

root=Path(__file__).resolve().parents[1]
for file in sorted((root/'web/test-results').glob('**/error-context.md')):
    print('RF_ERROR_CONTEXT '+str(file.relative_to(root)))
    print(file.read_text()[:12000])
images=sorted((root/'web/test-results').glob('**/test-failed-1.png'))[:2]+sorted((root/'artifacts').glob('qa-*.png'))
for file in images:
    data=base64.b64encode(file.read_bytes()).decode()
    key=file.stem if file.parent==root/'artifacts' else file.parent.name
    for i in range(0,len(data),12000):
        print('RF_PNG '+key+' '+str(i//12000)+' '+data[i:i+12000])
for name in ('e2e-api.log','e2e-worker.log'):
    file=root/'artifacts'/name
    if file.exists():
        print('RF_SERVICE_LOG '+name)
        print('\n'.join(file.read_text().splitlines()[-80:]))
