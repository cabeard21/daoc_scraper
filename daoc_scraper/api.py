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
