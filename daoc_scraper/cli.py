#!/usr/bin/env python3
"""
CLI entrypoint for daoc_scraper: scrape DAoC fight data and save into SQLite.
"""

import asyncio

import click
import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from daoc_scraper.database import async_session, engine
from daoc_scraper.models import fights, metadata, participants
from daoc_scraper.scraper import cleanup, fetch_fight_data, init_driver, login


# ------------------------------------------------------------------------------
async def init_db() -> None:
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


async def save_to_db(df: pd.DataFrame) -> None:
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
                        win=bool(row["Win"]),
                    )
                )

        await session.commit()


# ------------------------------------------------------------------------------
@click.command()
@click.option("--min-size", "-n", default=1, show_default=True, help="Min fight size")
@click.option("--max-size", "-x", default=1, show_default=True, help="Max fight size")
def scrape(min_size: int, max_size: int):
    """
    Scrape Eden DAoC fight data for fights of size MIN_SIZE v MAX_SIZE
    and upsert into an SQLite database.
    """
    # ensure DB & tables exist
    click.echo("Initializing database...")
    asyncio.run(init_db())

    # run scraper
    click.echo(f"Starting scraper for {min_size}v{max_size}…")
    driver = init_driver()
    try:
        token = login(driver)
        df = fetch_fight_data(
            driver=driver,
            min=min_size,
            max=max_size,
            token=token,
            known_ids=set(),  # DB dedupe will handle repeats
        )
    except Exception as e:
        click.echo(f"[ERROR] scraping failed: {e}", err=True)
        raise click.Abort()
    finally:
        cleanup(driver)

    if df.empty:
        click.echo("No new data fetched; exiting.")
        return

    click.echo(f"Fetched {len(df)} rows; saving to database…")
    asyncio.run(save_to_db(df))
    click.echo("Done.")


if __name__ == "__main__":
    scrape()
