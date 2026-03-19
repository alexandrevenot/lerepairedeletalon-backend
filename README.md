# Le Repaire de l'Étalon — Backend

![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.103+-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

REST API backend for **Le Repaire de l'Étalon**, an online platform operating in the equine industry by connecting stallion owners with mare owners for breeding services.

> Previously a business attempt, I am now using this project as a showcase of my computer science engineering skills.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)

---

## Overview

The platform handles:
- User authentication through access & refresh JWT
- Stallion profile management with photo storage (GCP Cloud Storage)
- Stallion search based on various equine criteria, including geolocation
- Cover (breeding) lifecycle, from request to payment
- Template-based contracts generation and online signature
- Payment processing via Stripe Connect

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database | MongoDB (pymongo) |
| Object Storage | Google Cloud Storage |
| Payments | Stripe Connect |
| Package Manager | uv |
| Linter | Ruff |
| Testing | pytest |

---

## Project Structure

```
server/
├── app/
│   ├── config.py              # Centralized settings via pydantic-settings
│   ├── dependencies.py        # FastAPI dependency injection (DB, GCP bucket)
│   ├── main.py                # App entrypoint, router registration
│   ├── monitoring/            # Telegram alerting
│   ├── etc/
│   │   └── geoloc/            # Static CSV data for French geolocation
│   ├── routers/
│   │   ├── auth/              # Register, login, JWT refresh
│   │   ├── stallions/         # Stallion CRUD, photo upload, search
│   │   ├── covers/            # Breeding request lifecycle
│   │   ├── contracts/         # Contract generation and e-signing
│   │   ├── payments/          # Stripe Connect accounts and webhooks
│   │   ├── users/             # User profile and legal identity
│   │   ├── mailing/           # Email verification and password reset
│   │   ├── stallion_owners/   # Stallion owner profiles
│   │   ├── geoloc/            # City and region lookup
│   │   └── admin/             # Admin routes
│   └── tests/
│       ├── conftest.py        # Fixtures (mongomock, FastAPI test clients)
│       ├── resources/         # Test assets (images)
│       └── test_*.py          # One test file per router
├── Dockerfile                 # Multi-stage build (uv + python:3.11-slim)
├── docker-compose.yml         # Traefik + backend + frontend
├── pyproject.toml             # Dependencies, build config, ruff and pytest settings
└── uv.lock                    # Locked dependency tree
```

---