"""Export the actual server contract without opening a database or provider connection."""
import json
from pathlib import Path

from researchflow.api.app import create_app
from researchflow.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
target = ROOT/'artifacts/openapi.json'
target.parent.mkdir(exist_ok=True)
schema = create_app(Settings(database_url='postgresql+psycopg://unused/unused')).openapi()
target.write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Exported actual API schema: {target}')
