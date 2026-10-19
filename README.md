# Bazart

A consumer-to-consumer marketplace for Uzbekistan where **every listing has a deadline**
(3, 5 or 7 days), so prices move instead of freezing for months.

Items are sold in one of two ways:

- **Price offers** (default): the seller sets a reference price per unit and a quantity; buyers
  propose their own price and quantity; the seller accepts, rejects or counters.
- **Auctions** (one unit): ascending (bids, proxy bidding, anti-sniping) or descending
  (the price drops on a schedule; the first buyer wins).

## Status

The platform works end to end on the `faza-e` branch, with 410 backend tests passing on real Postgres.
It is mid-way through **Faza E**: Bazart is moving to a **no-payment deal model**.

- Today: a sale creates an order with an escrow payment flow (hold, handover code, disputes).
- Target: a sale creates a **deal**, both sides see each other's verified contacts, and they settle
  between themselves. Bazart does not take part in payment. Revenue comes later from a seller
  wallet (commission, boosts).

Plan and progress: [`docs/FAZA_E_BAJARISH_TARTIBI.md`](docs/FAZA_E_BAJARISH_TARTIBI.md).
Deal model: [`docs/DEALS.md`](docs/DEALS.md).

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, Pydantic v2, Redis
  (rate limits, token blacklist, Celery broker), Celery (beat + workers), pytest, ruff.
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS v4, shadcn/ui, lucide-react
  (`frontend/`).
- **Notifications:** in-app and Telegram.

Money is always an integer number of tiyin (1 so'm = 100 tiyin) and is sent over the API as a
string. All arithmetic lives in `app/money/`.

## Running locally

```bash
docker compose up -d db redis minio          # Postgres on host port 5433
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
python scripts/seed_regions.py
python scripts/create_superadmin.py --email admin@bazart.uz --password '...'
uvicorn app.main:app --reload                # http://localhost:8000/docs

cd frontend && npm install && npm run dev    # http://localhost:3000
```

Background jobs in production run on Celery beat:
`celery -A app.core.celery_app worker` and `celery -A app.core.celery_app beat`.

## Checks

```bash
pytest                                       # needs the Postgres container
ruff check . && ruff format --check .
alembic upgrade head && alembic check        # on a clean database
cd frontend && npm run lint && npm run build
```

## Documentation

| File | About |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Rules for contributors and coding agents (Uzbek) |
| [`docs/FAZA_E_BAJARISH_TARTIBI.md`](docs/FAZA_E_BAJARISH_TARTIBI.md) | Faza E execution plan with progress |
| [`docs/DEALS.md`](docs/DEALS.md) | Deal model (target) |
| [`docs/OFFERS.md`](docs/OFFERS.md) | Price offers: negotiation, stock, concurrency |
| [`docs/AUCTION_ENGINE.md`](docs/AUCTION_ENGINE.md) | Bidding, proxy bids, anti-sniping, descending price |
| [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) | End-to-end walkthrough (pre-Faza E, with escrow) |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phases and open items |
| [`docs/DESIGN.md`](docs/DESIGN.md) | Frontend design system |
