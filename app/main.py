import yaml
from pymongo import MongoClient
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import middleware
import dependencies
import routers.auth.router as auth_router
import routers.stallions.router as stallions_router
import routers.covers.router as covers_router
import routers.geoloc.router as geoloc_router
import routers.payments.router as payments_router
import routers.contracts.router as contracts_router
import routers.users.router as users_router
import routers.mailing.router as mailing_router
import routers.admin.router as admin_router
import routers.stallion_owners.router as stallion_owners_router

with open('etc/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.on_event("startup")
async def start():
    dependencies.mongodb_client_instance = MongoClient(
        f"mongodb+srv://{config['db_username']}:{config['db_password']}@{config['mongo_url']}",
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
