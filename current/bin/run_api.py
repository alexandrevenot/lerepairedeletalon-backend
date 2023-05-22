import os
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import src.api.auth.router as auth_router

server = FastAPI()

server.include_router(auth_router.router)

origins = [
    "http://localhost:4200",
]

server.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

params = {
    "host": "localhost",
    "port": 3001
}

uv_config = uvicorn.Config(server, **params)
uv_server = uvicorn.Server(uv_config)
loop = asyncio.get_event_loop()
loop.run_until_complete(uv_server.serve())