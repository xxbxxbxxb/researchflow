import json
from uuid import uuid4

from starlette.exceptions import HTTPException


class BodyLimitMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope,receive,send)
        headers = dict(scope.get('headers',[]))
        multipart = headers.get(b'content-type',b'').lower().startswith(b'multipart/form-data')
        limit = 20 * 1024 * 1024 + 65536 if multipart else 128 * 1024
        length = headers.get(b'content-length')
        if length is not None and (not length.isdigit() or int(length)>limit):
            body = json.dumps({'code':'payload_too_large','message':'Request body exceeds its size limit.','request_id':uuid4().hex,'details':None}).encode()
            await send({'type':'http.response.start','status':413,'headers':[(b'content-type',b'application/json')]})
            await send({'type':'http.response.body','body':body})
            return
        size = 0
        async def bounded_receive():
            nonlocal size
            message = await receive()
            if message['type']=='http.request':
                size += len(message.get('body',b''))
                if size>limit:
                    raise HTTPException(413,'Request body exceeds its size limit.')
            return message
        await self.app(scope,bounded_receive,send)
