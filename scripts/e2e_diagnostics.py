"""Bounded diagnostics and actual browser images from synthetic CI fixtures."""
import asyncio
import base64
import os
import sys
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

async def failures():
    sys.path.insert(0,str(root/'src'))
    from sqlalchemy import text

    from researchflow.infrastructure.storage.database import Database
    url=os.getenv('RF_TEST_DATABASE_URL')
    if not url:
        return
    db=Database(url)
    try:
        async with db.session() as session:
            rows=await session.execute(text("SELECT kind,data FROM run_events WHERE kind IN ('failure','failed') ORDER BY event_id DESC LIMIT 10"))
            for kind,data in rows:
                print('RF_FAILURE',kind,data)
    finally:
        await db.close()

try:
    asyncio.run(failures())
except Exception:
    print('RF_FAILURE diagnostics unavailable')
