# api.py
from typing import Any

from database import async_session
from fastapi import FastAPI, HTTPException
from models import fights, participants
from sqlalchemy import select

app = FastAPI(title="DAoC Fight Data API")


@app.get("/fights/{fight_id}")
async def get_fight(fight_id: str) -> dict[str, Any]:
    async with async_session() as session:
        result = await session.execute(select(fights).where(fights.c.id == fight_id))
        fight = result.scalar_one_or_none()
        if not fight:
            raise HTTPException(404, "Fight not found")
        parts = await session.execute(
            select(participants).where(participants.c.fight_id == fight_id)
        )
        return {"fight": fight.fight_json, "participants": parts.all()}


@app.get("/fights/")
async def list_fights(skip: int = 0, limit: int = 100) -> list[Any]:
    async with async_session() as session:
        result = await session.execute(
            select(fights).offset(skip).limit(limit).order_by(fights.c.date.desc())
        )
        return result.scalars().all()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",  # module:variable
        host="0.0.0.0",
        port=8000,
        reload=True,  # dev hot‐reload
    )
