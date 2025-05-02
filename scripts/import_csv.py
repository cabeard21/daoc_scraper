#!/usr/bin/env python3
import asyncio
import os
import sys

# make sure “your-project” is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd

from daoc_scraper.cli import save_to_db  # re-uses your async save logic
from daoc_scraper.database import engine
from daoc_scraper.models import metadata


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)


def normalize_csv(path: str) -> list[tuple[pd.DataFrame, int, int]]:
    """
    Reads the buddy CSV and returns a list of tuples:
      (df_flat, min_size, max_size)
    where df_flat has columns [ID, Class, Win, Date].
    """
    raw = pd.read_csv(path, sep=None, engine="python")  # auto-detects delimiter
    imports = []
    for fight_id, grp in raw.groupby("ID"):
        # pull the fight size out of the "Type" column, e.g. "8v8"
        type_str = grp["Type"].iloc[0]
        min_size, max_size = (int(x) for x in type_str.split("v"))
        rows = []
        for _, row in grp.iterrows():
            winner_flag = bool(row["Winner"])
            # split the comma-separated Classes into one row per class
            for cls in row["Classes"].split(","):
                rows.append(
                    {
                        "ID": fight_id,
                        "Class": cls.strip(),
                        "Win": winner_flag,
                        "Date": row["Date"],
                    }
                )
        df_flat = pd.DataFrame(rows)

        # normalize to ISO-8601 + UTC offset so it matches the scraper output
        df_flat["Date"] = (
            pd.to_datetime(df_flat["Date"])  # parse "4/16/2025", etc.
            .dt.tz_localize("UTC")  # make it timezone-aware
            .dt.strftime("%Y-%m-%dT%H:%M:%S%z")  # format as "2025-04-16T00:00:00+0000"
        )

        imports.append((df_flat, min_size, max_size))
    return imports


async def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python import_csv.py path/to/buddy.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    print("Initializing database…")
    await init_db()

    for df_flat, min_size, max_size in normalize_csv(csv_path):
        print(f"Importing fight {df_flat['ID'].iloc[0]} (size {min_size}v{max_size})…")
        # this will upsert into `fights` and insert participants
        await save_to_db(df_flat, min_size, max_size)

    print("Import complete.")


if __name__ == "__main__":
    asyncio.run(main())
