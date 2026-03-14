from pymongo import MongoClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from . import middleware
from . import dependencies
from .routers.auth import router as auth_router
from .routers.stallions import router as stallions_router
from .routers.covers import router as covers_router
from .routers.geoloc import router as geoloc_router
from .routers.payments import router as payments_router
from .routers.contracts import router as contracts_router
from .routers.users import router as users_router
from .routers.mailing import router as mailing_router
from .routers.admin import router as admin_router
from .routers.stallion_owners import router as stallion_owners_router

from app.config import settings

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.on_event("startup")
async def start():
    dependencies.mongodb_client_instance = MongoClient(
        f"mongodb+srv://{settings.db_username}:{settings.db_password}@{settings.mongo_url}",
        tls=True
    )

@app.on_event("shutdown")
async def stop():
    dependencies.mongodb_client_instance.close()

app.include_router(auth_router.router, tags=["Auth"])
app.include_router(stallions_router.router, tags=["Stallions"])
app.include_router(covers_router.router, tags=["Covers"])
app.include_router(geoloc_router.router, tags=["Geoloc"])
app.include_router(payments_router.router, tags=["Payments"])
app.include_router(contracts_router.router, tags=["Contracts"])
app.include_router(users_router.router, tags=["Users"])
app.include_router(mailing_router.router, tags=["Mailing"])
app.include_router(admin_router.router, tags=["Admin"])
app.include_router(stallion_owners_router.router, tags=["Stallion Owners"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    BaseHTTPMiddleware,
    dispatch=middleware.Middleware()
)
