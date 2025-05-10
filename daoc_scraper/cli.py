#!/usr/bin/env python3
"""
CLI entrypoint for daoc_scraper: scrape DAoC fight data and save into SQLite.
"""

import asyncio
import os

import click
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from daoc_scraper.database import async_session, engine
from daoc_scraper.models import fights, metadata, participants
from daoc_scraper.scraper import cleanup, fetch_fight_data, init_driver, login

load_dotenv()


# ------------------------------------------------------------------------------
async def init_db() -> None:
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def save_to_db(df: pd.DataFrame, min_size: int, max_size: int) -> None:
    """
    Given the flat DataFrame with columns [ID, Class, Win, Date],
    group by ID to insert into fights + participants.
    """
    async with async_session() as session:
        for fight_id, group in df.groupby("ID"):
            # fight date is same for all rows in this group
            fight_date = pd.to_datetime(group["Date"].iloc[0])

            # prepare upsert for fights
            stmt = (
                sqlite_insert(fights)
                .values(
                    id=fight_id,
                    fight_json=group.to_dict(orient="records"),
                    date=fight_date,
                    min_size=min_size,
                    max_size=max_size,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            await session.execute(stmt)

            # insert participants
            for _, row in group.iterrows():
                await session.execute(
                    participants.insert()
                    .prefix_with("OR IGNORE")
                    .values(
                        fight_id=fight_id,
                        class_name=row["Class"],
                        name=row["Name"],
                        win=bool(row["Win"]),
                    )
                )

        await session.commit()


# ------------------------------------------------------------------------------
@click.command()
@click.option("--min-size", "-n", default=1, show_default=True, help="Min fight size")
@click.option("--max-size", "-x", default=1, show_default=True, help="Max fight size")
def scrape(min_size: int, max_size: int) -> None:
    """
    Scrape Eden DAoC fight data for fights of size MIN_SIZE v MAX_SIZE
    and upsert into an SQLite database.
    """
    # ensure DB & tables exist
    click.echo("Initializing database...")
    asyncio.run(init_db())

    # run scraper
    click.echo(f"Starting scraper for {min_size}v{min_size} to {max_size}v{max_size}…")
    driver = init_driver(os.getenv("HEADLESS", "false") == "true")
    try:
        token = login(driver)
        for fight_size in range(min_size, max_size + 1):
            click.echo(f"Scraping {fight_size}v{fight_size}…")
            df = fetch_fight_data(
                driver=driver,
                min=fight_size,
                max=fight_size,
                token=token,
                known_ids=set(),  # DB dedupe will handle repeats
            )
            if df.empty:
                click.echo(
                    f"No new data fetched for {fight_size}v{fight_size}; skipping…"
                )
                continue

            click.echo(
                f"Fetched {len(df)} rows for {fight_size}v{fight_size}; "
                f"saving to database…"
            )
            asyncio.run(save_to_db(df, fight_size, fight_size))
    except Exception as e:
        click.echo(f"[ERROR] scraping failed: {e}", err=True)
        raise click.Abort()
    finally:
        cleanup(driver)

    click.echo("Done.")


if __name__ == "__main__":
    scrape()
