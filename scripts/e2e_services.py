"""Owned API/Worker and disposable real PostgreSQL test setup for Playwright."""
import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path

from argon2 import PasswordHasher
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


async def reset_database(url: str) -> None:
    from researchflow.infrastructure.storage.database import Database
    from researchflow.infrastructure.storage.models import Base
    if not (make_url(url).database or '').endswith('_test'):
        raise ValueError('E2E requires a dedicated database ending in _test')
    database = Database(url)
    try:
        async with database.engine.begin() as connection:
            await connection.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text('DROP TABLE IF EXISTS alembic_version'))
    finally:
        await database.close()


def demo_pdf(target: Path) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=600,height=300)
    font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 20 200 Td (The synthetic study used a sample size of 12, only for Chinese text.) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.add_page(PdfReader(ROOT/'tests/fixtures/sources/chinese-two-pages.pdf').pages[1])
    with target.open('wb') as output:
        writer.write(output)


def main() -> None:
    url = os.environ.get('RF_TEST_DATABASE_URL')
    if not url:
        raise ValueError('Set RF_TEST_DATABASE_URL for real E2E; no mock database is used')
    artifacts = ROOT/'artifacts'
    artifacts.mkdir(exist_ok=True)
    demo_pdf(artifacts/'research-demo.pdf')
    asyncio.run(reset_database(url))
    env = {**os.environ,'RF_DATABASE_URL':url,'RF_MODE':'demo','RF_PASSWORD_HASH':PasswordHasher().hash('test-password-1234'),'RF_ALLOWED_ORIGINS':'http://localhost:5173,http://127.0.0.1:5173','RF_BLOB_ROOT':str(ROOT/'.researchflow-data/e2e-blobs')}
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,check=True)
    children = []
    files = []
    def stop(signum,frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    try:
        for name,args in [('api',['serve','--host','127.0.0.1']),('worker',['worker','--mode','demo'])]:
            output = (artifacts/f'e2e-{name}.log').open('w')
            files.append(output)
            children.append(subprocess.Popen([sys.executable,'-m','researchflow.cli',*args],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT))
        while True:
            for child in children:
                if child.poll() is not None:
                    raise RuntimeError('E2E API/Worker stopped unexpectedly; see artifacts logs')
            try:
                children[0].wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for file in files:
            file.close()


if __name__=='__main__':
    main()
