# api.py
from datetime import date
from typing import Any

from database import async_session
from fastapi import FastAPI, HTTPException, Query
from models import fights, participants
from sqlalchemy import and_, select

app = FastAPI(title="DAoC Fight Data API")


@app.get("/fights/{fight_id}")
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


@app.get("/fights/")
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",  # module:variable
        host="0.0.0.0",
        port=8000,
        reload=True,  # dev hot‐reload
    )
