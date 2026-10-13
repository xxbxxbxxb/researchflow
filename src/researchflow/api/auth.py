import asyncio
import secrets
from hashlib import sha256

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from fastapi import APIRouter,Request,Response,Depends

from researchflow.api.errors import APIError
from researchflow.api.schemas import LoginInput,AuthSessionResponse
from researchflow.domain.access import Principal
from researchflow.infrastructure.storage.session_repository import LoginRateLimitedError

router = APIRouter(prefix='/api/auth',tags=['auth'])


def check_origin(request: Request) -> None:
    if request.headers.get('origin') not in request.app.state.settings.allowed_origins:
        raise APIError(403,'origin_denied','Request origin is not allowed.')


async def require_principal(request: Request) -> Principal:
    token = request.cookies.get('rf_session')
    if not token:
        raise APIError(401,'authentication_required','Sign in to continue.')
    session = await request.app.state.resources.sessions.lookup(token)
    if session is None:
        raise APIError(401,'authentication_required','Session expired. Sign in again.')
    principal,csrf_hash = session
    if request.method not in {'GET','HEAD','OPTIONS'}:
        check_origin(request)
        provided = request.headers.get('x-csrf-token','')
        if not provided or not secrets.compare_digest(sha256(provided.encode()).hexdigest(),csrf_hash):
            raise APIError(403,'csrf_denied','CSRF token is invalid.')
    return principal


async def require_project(request: Request, project_id: str, principal: Principal = Depends(require_principal)) -> str:
    if not principal.allows(project_id) or await request.app.state.resources.research.get_project(project_id) is None:
        raise APIError(404,'not_found','Project was not found.')
    return project_id


@router.post('/login',response_model=AuthSessionResponse)
async def login(data: LoginInput, request: Request, response: Response):
    check_origin(request)
    settings = request.app.state.settings
    if not settings.password_hash:
        raise APIError(409,'configuration_missing','Configure RF_PASSWORD_HASH before signing in.')
    # Only the actual peer is used. User supplied forwarding headers have no authority.
    source = request.client.host if request.client else 'unknown'
    resources = request.app.state.resources
    async with request.app.state.login_semaphore:
        try:
            key = await resources.sessions.begin_login(source)
        except LoginRateLimitedError as exc:
            raise APIError(429,'login_rate_limited','Too many failed sign-in attempts. Try again in one minute.') from exc
        success = False
        try:
            try:
                success = await asyncio.to_thread(PasswordHasher().verify,settings.password_hash,data.password)
            except (VerificationError,InvalidHashError):
                success = False
        finally:
            await resources.sessions.end_login(key,success)
        if not success:
            raise APIError(401,'invalid_credentials','Sign-in failed.')
        token,csrf = await resources.sessions.create()
    response.set_cookie('rf_session',token,max_age=8*3600,httponly=True,secure=settings.secure_cookies,samesite='lax',path='/')
    response.set_cookie('rf_csrf',csrf,max_age=8*3600,secure=settings.secure_cookies,samesite='strict',path='/')
    return {'actor_id':'local-user','csrf_token':csrf,'execution_mode':settings.execution_mode}


@router.get('/session',response_model=AuthSessionResponse)
async def session_info(request: Request, principal: Principal = Depends(require_principal)):
    return {'actor_id':principal.actor_id,'csrf_token':request.cookies.get('rf_csrf',''),'execution_mode':request.app.state.settings.execution_mode}


@router.post('/logout',dependencies=[Depends(require_principal)])
async def logout(request: Request,response: Response):
    await request.app.state.resources.sessions.revoke(request.cookies['rf_session'])
    response.delete_cookie('rf_session',path='/')
    response.delete_cookie('rf_csrf',path='/')
    return {'signed_out':True}
