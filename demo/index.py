import asyncio

import numpy as np
import pandas as pd
from js import JSON, Object, Plotly, String, document, fetch
from pyodide.ffi import create_proxy, to_js

API_BASE = "https://www.daocapi.com"


def update_status(msg: str) -> None:
    document.getElementById("status").innerText = msg


async def get_fight_data(
    api_key: str, min_size: int = 8, max_size: int = 8
) -> pd.DataFrame:
    update_status("Fetching IDs...")
    # 1. Get IDs
    options = Object.fromEntries(
        [["headers", Object.fromEntries([["X-API-Key", api_key]])]]
    )

    params = f"?min_size={min_size}&max_size={max_size}&limit=500"
    response = await fetch(f"{API_BASE}/fights/{params}", options)
    id_list = await response.json()

    if not id_list:
        update_status("No fights found.")
        return pd.DataFrame()
    # 2. POST /fights/bulk for fight data
    update_status(f"Fetched {len(id_list)} IDs, requesting bulk data...")

    # Force payload to a JS string and headers to JS object
    payload = JSON.stringify({"ids": id_list})
    print("Payload type:", type(payload))
    print("Payload value:", payload)

    post_options = Object.fromEntries(
        [
            ["method", "POST"],
            [
                "headers",
                Object.fromEntries(
                    [
                        ["X-API-Key", api_key],
                        ["Content-Type", "application/json"],
                    ]
                ),
            ],
            ["body", payload],
        ]
    )
    resp2 = await fetch(f"{API_BASE}/fights/bulk", post_options)
    bulk = await resp2.json()

    # 3. Flatten data to rows
    rows = []
    for fight_id, payload in bulk.items():
        for p in payload["participants"]:
            rows.append(
                {
                    "ID": fight_id,
                    "Class": p["class_name"],
                    "Win": p["win"],
                    "Name": p.get("name", "Unknown"),
                }
            )
    df = pd.DataFrame(rows)
    update_status(f"Loaded {len(df)} rows from API.")
    return df


def analyze_data(df: pd.DataFrame) -> None:
    class_counts = df["Class"].value_counts()
    plot_data = [
        dict(
            type="bar",
            x=class_counts.index.tolist(),
            y=class_counts.values.tolist(),
            marker=dict(color="blue"),
        )
    ]
    Plotly.newPlot("plot", to_js(plot_data), to_js({"title": "Class Distribution"}))
    win_rates = df.groupby("Class")["Win"].mean().reset_index()
    n = df.groupby("Class")["Win"].count().reset_index(name="n")["n"]
    p = win_rates["Win"]
    z = 1.96
    z2 = z**2
    ci_lower = (p + z2 / (2 * n) - z * np.sqrt(p * (1 - p) / n + z2 / (4 * n**2))) / (
        1 + z2 / n
    )
    win_rates["Wilson_Lower"] = ci_lower
    plot_data2 = [
        dict(
            type="bar",
            x=win_rates["Class"].tolist(),
            y=win_rates["Win"].tolist(),
            error_y=dict(
                type="data",
                array=(win_rates["Win"] - win_rates["Wilson_Lower"]).tolist(),
                visible=True,
            ),
            marker=dict(color="green"),
        )
    ]
    Plotly.newPlot("plot2", to_js(plot_data2), to_js({"title": "Win Rate per Class"}))


def on_fetch_click(event=None) -> None:
    # Use asyncio.create_task to run coroutine
    asyncio.create_task(fetch_and_analyze())


async def fetch_and_analyze() -> None:
    api_key = document.getElementById("api-key-input").value
    api_key = api_key.strip()
    if not api_key:
        update_status("Please enter your API key.")
        return
    update_status("Starting data fetch...")
    try:
        df = await get_fight_data(api_key)
        if len(df):
            analyze_data(df)
        else:
            update_status("No data to analyze.")
    except Exception as e:
        update_status(f"Error: {e}")


# Setup button
button = document.getElementById("fetch-btn")
button.addEventListener("click", create_proxy(on_fetch_click))
