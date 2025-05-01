# api.py
import logging
import os
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import APIKeyHeader
from sqlalchemy import and_, select
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from daoc_scraper.database import async_session
from daoc_scraper.models import fights, participants

app = FastAPI(
    title="DAoC Fight Data API",
    docs_url=None,  # disable Swagger UI
    redoc_url=None,  # disable ReDoc
    openapi_url=None,  # disable OpenAPI schema
)

# Trust X-Forwarded headers from Nginx
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Only allow Host headers matching your domain
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "68.183.151.160.nip.io",  # your nip.io hostname
        "localhost",  # for local dev, if you need it
        "127.0.0.1",  # if you ever curl inside the container
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.com"],  # your client
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: str = Security(api_key_header)) -> str:
    secret = os.getenv("DAOC_API_KEY")
    if not key or key != secret:
        raise HTTPException(403, detail="Invalid or missing API Key")
    return key


router = APIRouter(dependencies=[Depends(require_api_key)])


@app.on_event("startup")
async def list_routes() -> None:
    routes = [route.path for route in app.router.routes]
    logging.getLogger("uvicorn.error").info(f"Registered routes: {routes}")


@router.get("/fights/{fight_id}")
async def get_fight(fight_id: str) -> dict[str, Any]:
    async with async_session() as session:
        # select just the JSON payload
        result = await session.execute(
            select(fights.c.fight_json).where(fights.c.id == fight_id)
        )
        fight_json = result.scalar_one_or_none()
        if fight_json is None:
            raise HTTPException(404, "Fight not found")

        # fetch participants
        parts = await session.execute(
            select(participants.c.class_name, participants.c.win).where(
                participants.c.fight_id == fight_id
            )
        )
        # turn them into list[dict]
        participants_list = [
            {"class_name": cls, "win": win} for cls, win in parts.all()
        ]

    return {"fight": fight_json, "participants": participants_list}


@router.get("/fights/")
async def list_fights(
    min_size: int | None = Query(None, description="Minimum size of the fight"),
    max_size: int | None = Query(None, description="Maximum size of the fight"),
    date_from: date | None = Query(None, description="Filter fights from this date"),
    date_to: date | None = Query(None, description="Filter fights to this date"),
    skip: int = 0,
    limit: int = 100,
) -> list[str]:
    q = select(fights)
    filters = []
    if min_size is not None:
        filters.append(fights.c.min_size >= min_size)
    if max_size is not None:
        filters.append(fights.c.max_size <= max_size)
    if date_from is not None:
        filters.append(fights.c.date >= date_from)
    if date_to is not None:
        filters.append(fights.c.date <= date_to)
    if filters:
        q = q.where(and_(*filters))

    q = q.order_by(fights.c.date.desc()).offset(skip).limit(limit)

    async with async_session() as session:
        result = await session.execute(q)
        rows = result.mappings().all()
        return [row["id"] for row in rows]


app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",  # module:variable
        host="0.0.0.0",
        port=8000,
        reload=True,  # dev hot‐reload
    )
