import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from sqlalchemy import text

from researchflow.api import auth,projects,sources,tasks,runs,reports,events
from researchflow.api.errors import APIError
from researchflow.api.limits import BodyLimitMiddleware
from researchflow.composition import api_resources
from researchflow.domain.errors import EvidenceConflict,ProjectBoundaryError
from researchflow.infrastructure.storage.database import Database
from researchflow.ports.runtime import InputVersionMismatchError
from researchflow.settings import Settings


def error_response(request: Request,status: int,code: str,message: str,details=None):
    return JSONResponse({'code':code,'message':message,'request_id':getattr(request.state,'request_id',uuid4().hex),'details':details},status_code=status)


def create_app(settings: Settings,database: Database | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        async with api_resources(settings,database) as resources:
            app.state.resources = resources
            yield
    app = FastAPI(title='ResearchFlow',version='1.0.0',lifespan=lifespan)
    app.state.settings = settings
    app.state.login_semaphore = asyncio.Semaphore(2)
    app.add_middleware(CORSMiddleware,allow_origins=list(settings.allowed_origins),allow_credentials=True,allow_methods=['GET','POST','OPTIONS'],allow_headers=['Content-Type','X-CSRF-Token','Idempotency-Key','Last-Event-ID'])
    app.add_middleware(BodyLimitMiddleware)

    @app.middleware('http')
    async def request_identity(request,call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers['x-request-id'] = request.state.request_id
        response.headers['x-content-type-options'] = 'nosniff'
        response.headers['referrer-policy'] = 'same-origin'
        return response

    @app.exception_handler(APIError)
    async def api_error(request,exc):
        return error_response(request,exc.status,exc.code,exc.message,exc.details)

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        return error_response(request,exc.status_code,'payload_too_large' if exc.status_code==413 else 'request_denied',str(exc.detail))

    async def validation_error(request,exc):
        details = [{'location':list(e['loc']),'message':e['msg'],'type':e['type']} for e in exc.errors()[:20]]
        return error_response(request,422,'invalid_input','Request fields are invalid.',details)
    app.add_exception_handler(RequestValidationError,validation_error)
    app.add_exception_handler(ValidationError,validation_error)

    @app.exception_handler(ValueError)
    async def domain_error(request,exc):
        if isinstance(exc,EvidenceConflict):
            return error_response(request,409,'immutable_conflict','Stored research content conflicts with this identity.')
        if isinstance(exc,ProjectBoundaryError):
            return error_response(request,404,'not_found','Referenced material was not found in this project.')
        return error_response(request,400,'invalid_operation',str(exc))

    @app.exception_handler(InputVersionMismatchError)
    async def version_error(request,exc):
        return error_response(request,409,'input_version_mismatch',str(exc))

    @app.get('/health')
    async def health(request: Request):
        try:
            async with request.app.state.resources.database.session() as session:
                await session.execute(text('SELECT 1'))
                version = await session.scalar(text('SELECT version_num FROM alembic_version'))
            if version != '0004':
                return JSONResponse({'status':'not_ready','schema':'migration_required'},status_code=503)
            return {'status':'ready','schema_version':version}
        except Exception:
            return JSONResponse({'status':'not_ready','database':'unavailable'},status_code=503)

    for router in (auth.router,projects.router,sources.router,tasks.router,runs.router,reports.router,events.router):
        app.include_router(router)
    return app


def app_factory() -> FastAPI:
    return create_app(Settings.from_env())
