#!/usr/bin/env python3
"""
scheduler.py

Run the daoc_scraper.cli scrape command for 1v1, 2v2, … 8v8 at a fixed interval.
"""

import subprocess
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Use the same Python that launched this script
PYTHON = sys.executable
CLI_MODULE = "daoc_scraper.cli"


def scrape_size(size: int) -> None:
    """Invoke the CLI for a given fight size (size v size)."""
    subprocess.run(
        [
            PYTHON,
            "-m",
            CLI_MODULE,
            "--min-size",
            str(size),
            "--max-size",
            str(size),
        ],
        check=True,
    )


if __name__ == "__main__":
    # Create a scheduler that runs jobs in the foreground
    scheduler = BlockingScheduler()

    # How often to run (e.g. every hour)
    INTERVAL_HOURS = 1

    # Schedule one job per fight-size from 1v1 through 8v8
    for i in range(1, 9):
        minute_offset = (i - 1) * 7  # 0, 7, 14, 21, …
        trigger = CronTrigger(minute=str(minute_offset), hour="*")
        scheduler.add_job(
            scrape_size,
            trigger=trigger,
            args=[i],
            id=f"cron_scrape_{i}v{i}",
            name=f"Cron‐Scrape {i}v{i}",
        )

    print(f"Starting scheduler: scraping every {INTERVAL_HOURS}h for sizes 1v1–8v8")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")
