import os

import pandas as pd
from sqlalchemy import create_engine

DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///data/fights.db")
DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

engine = create_engine(DB_PATH.replace("sqlite+aiosqlite", "sqlite"))  # for pandas


def export_size(size: int) -> None:
    # Query all participant records for this fight size
    sql = f"""
    SELECT p.fight_id AS ID, p.class_name AS Class, p.name AS Name, p.win AS Win, f.date AS Date
    FROM fights f
    JOIN fight_participants p ON f.id = p.fight_id
    WHERE f.min_size = {size} AND f.max_size = {size}
    """
    df = pd.read_sql(sql, engine)
    out_path = os.path.join(DATA_DIR, f"fights-{size}v{size}.json")
    df.to_json(out_path, orient="records", date_format="iso")
    print(f"Wrote {len(df)} records to {out_path}")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    for size in range(1, 9):
        export_size(size)
