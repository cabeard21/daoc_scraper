#!/usr/bin/env python3
"""
scheduler.py

Run the daoc_scraper.cli scrape command for 1v1, 2v2, … 8v8 at a fixed interval.
"""

import subprocess
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

# Use the same Python that launched this script
PYTHON = sys.executable
CLI_MODULE = "daoc_scraper.cli"


def scrape_all_sizes() -> None:
    """Invoke the CLI for all fight sizes (1v1 through 8v8)."""
    subprocess.run(
        [
            PYTHON,
            "-m",
            CLI_MODULE,
            "--min-size",
            "1",
            "--max-size",
            "8",
        ],
        check=True,
    )


if __name__ == "__main__":
    # Create a scheduler that runs jobs in the foreground
    scheduler = BlockingScheduler()

    # How often to run (e.g. every hour)
    INTERVAL_HOURS = 1
    JITTER_SECONDS = 600

    # Schedule one job to scrape all sizes (1v1 through 8v8) once every hour
    scheduler.add_job(
        scrape_all_sizes,
        trigger="interval",
        hours=INTERVAL_HOURS,
        jitter=JITTER_SECONDS,
        id="scrape_all_sizes",
        name="Scrape All Sizes (1v1–8v8)",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(),
        misfire_grace_time=600,
    )

    print(f"Starting scheduler: scraping all sizes every {INTERVAL_HOURS}h")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")
