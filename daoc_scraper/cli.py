#!/usr/bin/env python3
"""
CLI entrypoint for daoc_scraper: scrape DAoC fight data and save to CSV.
"""

from pathlib import Path

import click
import pandas as pd

from daoc_scraper.scraper import cleanup, fetch_fight_data, init_driver, login


@click.command()
@click.option(
    "--min-size",
    "-n",
    "min_size",
    default=1,
    show_default=True,
    type=int,
    help="Minimum fight size to scrape (e.g. 1 for 1v1).",
)
@click.option(
    "--max-size",
    "-x",
    "max_size",
    default=1,
    show_default=True,
    type=int,
    help="Maximum fight size to scrape (e.g. 1 for 1v1).",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    default=None,
    help="Where to write the CSV. Defaults to data/{min}v{max}_fight_data.csv",
)
def scrape(min_size: int, max_size: int, output: str | None = None) -> None:
    """
    Scrape Eden DAoC fight data for fights of size MIN_SIZE v MAX_SIZE,
    append to existing CSV (if any), and save the result.
    """
    # decide on output file
    if output is None:
        output = f"data/{min_size}v{max_size}_fight_data.csv"
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # load existing data so we can skip known IDs
    if out_path.exists():
        click.echo(f"Loading existing data from {out_path}")
        existing_df = pd.read_csv(out_path)
        known_ids = set(existing_df["ID"].astype(str))
    else:
        existing_df = pd.DataFrame()
        known_ids = set()

    # spin up Selenium, log in, fetch new fights
    driver = init_driver()
    try:
        click.echo("Logging in to Eden DAoC…")
        token = login(driver)

        click.echo(f"Fetching fight data for {min_size}v{max_size}…")
        new_df = fetch_fight_data(
            driver=driver,
            min=min_size,
            max=max_size,
            token=token,
            known_ids=known_ids,
        )
    except Exception as e:
        click.echo(f"Error during scraping: {e}", err=True)
        raise click.Abort()
    finally:
        click.echo("Cleaning up driver…")
        cleanup(driver)

    # combine and de-dupe
    if not new_df.empty:
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined.drop_duplicates(subset=["ID"], inplace=True)
        combined.to_csv(out_path, index=False)
        click.echo(f"Wrote {len(combined)} total rows to {out_path}")
    else:
        click.echo("No new fights found; nothing to write.")


if __name__ == "__main__":
    scrape()
