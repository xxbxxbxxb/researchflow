from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class WorkspaceStaticFiles(StaticFiles):
    async def get_response(self,path,scope):
        if path.startswith(('api/','health')):
            raise HTTPException(404)
        try:
            return await super().get_response(path,scope)
        except HTTPException as exc:
            if exc.status_code!=404 or Path(path).suffix:
                raise
            return await super().get_response('index.html',scope)
