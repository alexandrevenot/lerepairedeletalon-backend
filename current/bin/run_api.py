import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
from app import middleware

dirs = ["log", "run"]
for d in dirs:
    p = f"/lerepairedeletalon/server/import/var/{d}/API/"
    if not os.path.isdir(p):
        os.mkdir(p)

import app.auth.router as auth_router
import app.stallions.router as stallions_router
import app.covers.router as covers_router
import app.geoloc.router as geoloc_router
import app.pricing.router as pricing_router
import app.contracts.router as contracts_router
import app.users.router as users_router
import app.mailing.router as mailing_router
import app.admin.router as admin_router

server = FastAPI()

server.include_router(auth_router.router, tags=["Auth"])
server.include_router(stallions_router.router, tags=["Stallions"])
server.include_router(covers_router.router, tags=["Covers"])
server.include_router(geoloc_router.router, tags=["Geoloc"])
server.include_router(pricing_router.router, tags=["Pricing"])
server.include_router(contracts_router.router, tags=["Contracts"])
server.include_router(users_router.router, tags=["Users"])
server.include_router(mailing_router.router, tags=["Mailing"])
server.include_router(admin_router.router, tags=["Admin"])

origins = [
    "http://localhost:4200",
    "https://esignatures.io"
]

server.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

server.add_middleware(
    BaseHTTPMiddleware,
    dispatch=middleware.Middleware()
)

params = {
    "host": "localhost",
    "port": 3001
}

uv_config = uvicorn.Config(server, **params)
uv_server = uvicorn.Server(uv_config)
loop = asyncio.get_event_loop()
loop.run_until_complete(uv_server.serve())
