from fastapi import Request


class Middleware:
    async def __call__(self, request: Request, call_next):
        return await call_next(request)
