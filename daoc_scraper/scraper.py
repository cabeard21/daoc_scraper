import asyncio
import os
from enum import Enum
from functools import partial
from typing import Any

import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from limits import RateLimitItemPerSecond
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()


class Realm(Enum):
    ALL = "all"
    HIB = "hib"
    MID = "mid"
    ALB = "alb"


def init_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    # required for unprivileged containers
    options.add_argument("--no-sandbox")

    # disable GPU
    options.add_argument("--disable-gpu")

    # Legacy headless mode (not the “new” headless)
    if headless:
        options.add_argument("--headless")

    return webdriver.Chrome(options=options)


def is_logged_in(driver: WebDriver) -> bool:
    """Check if the user is still logged in by looking for a specific element
    on the page."""
    try:
        # Check for an element that is only visible when logged in, like a
        # username or logout button
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='username_logged_in']"))
        )
        return True
    except Exception:
        # If the element is not found, assume the session has expired
        return False


def login(driver: WebDriver) -> str:
    """Login to the Eden DAOC website using the credentials stored in the secrets file.

    Returns:
        str: the authentication token for the session.
    """
    # Navigate to the website
    driver.get("https://eden-daoc.net/herald")

    # If already logged in, return the current token
    if is_logged_in(driver):
        # Retrieve the existing token from cookies
        token: dict[str, str] | None = driver.get_cookie("eden_daoc_sid")
        if token:
            return token["value"]

    # Initiate login
    login_button = driver.find_element(By.CLASS_NAME, "special-header-item")
    login_button.click()

    # Wait for the login page to load and authenticate
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
    email_field = driver.find_element(By.NAME, "email")
    password_field = driver.find_element(By.NAME, "password")
    email_field.send_keys(os.getenv("DS_EMAIL"))
    password_field.send_keys(os.getenv("DS_PASSWORD"))
    password_field.send_keys(Keys.RETURN)

    # Handle Permissions if necessary
    authorize_button_xpath = (
        "/html/body/div[2]/div[2]/div[1]/div[1]/div/div/div/div/div[2]/div/div/button"
    )
    authorize_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, authorize_button_xpath))
    )
    authorize_button.click()

    # Wait for login to complete
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "username"))
    )

    # Extract the authentication token
    token: dict[str, str] | None = driver.get_cookie("eden_daoc_sid")  # type: ignore
    if token is None:
        raise ValueError("Failed to extract authentication token")

    return token["value"]


def parse_row(row: Any) -> dict[str, str]:
    cells = row.find_all("td")
    return {
        "Rank": cells[0].text.strip(),
        "Name": cells[1].text.strip(),
        "Class": cells[3].text.strip(),
        "Guild": cells[5].text.strip(),
        "Level": cells[6].text.strip(),
        "Realm Points": cells[7].text.strip(),
        "Realm Title": cells[8].text.strip(),
        "LWSK": cells[9].text.strip(),
        "LWRP": cells[10].text.strip(),
        "RR": cells[11].text.strip(),
    }


def fetch_data(driver: WebDriver, realm: Realm = Realm.ALL) -> pd.DataFrame:
    # Access the data page
    realm_token = f"&r={realm.value}" if realm != Realm.ALL else ""
    driver.get(f"https://eden-daoc.net/herald?n=top_lwsk{realm_token}")

    # Wait for the first data row in the table to be visible
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "#tops_content tr:not(:first-child)")
            )
        )
    except TimeoutException:
        raise Exception("Timed out waiting for table rows to be visible")

    # Scrape the data
    table_div = driver.find_element(By.ID, "tops_content")
    table_div_html = table_div.get_attribute("innerHTML")  # type: ignore
    if table_div_html is None:
        raise StaleElementReferenceException("Table content not found")

    soup = BeautifulSoup(table_div_html, "html.parser")
    table = soup.find("table")
    if table is None:
        raise ValueError("Table element not found")

    data: list[dict[str, str]] = []
    for row in table.find_all("tr")[1:]:  # Skip the header row # type: ignore
        row_data = parse_row(row)
        data.append(row_data)

    df = pd.DataFrame(data)
    return df


def fetch_daoc_config(headers: dict[str, Any]) -> dict[str, str]:
    url = "https://eden-daoc.net/chrplan/daoc.json"

    async def fetch_daoc_config_async() -> dict[str, str]:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                return await response.json()

    return asyncio.run(fetch_daoc_config_async())


def create_id_to_class_name_mapping(daoc_config: dict[str, Any]) -> dict[int, str]:
    # Create an inverted mapping of class IDs to class names
    id_to_class_name: dict[int, str] = {}
    for class_name, details in daoc_config["classes"].items():
        class_id = details["id"]
        id_to_class_name[class_id] = class_name
    return id_to_class_name


def extract_fight_details(
    fight_json: dict[str, Any],
    id_to_class_name: dict[int, str],
) -> pd.DataFrame:
    # Extract date from the 's' key
    fight_date: str = fight_json["s"]

    # Prepare lists to hold DataFrame data
    ids: list[str] = []
    class_names: list[str] = []
    wins: list[bool] = []
    dates: list[str] = []

    # Iterate through winning side 'a'
    for participant in fight_json["a"]["p"]:
        class_id = participant["c"]
        class_names.append(id_to_class_name.get(class_id, "Unknown"))
        wins.append(True)  # These participants are winners
        dates.append(fight_date)
        ids.append(fight_json["id"])

    # Iterate through losing side 'b'
    for participant in fight_json["b"]["p"]:
        class_id = participant["c"]
        class_names.append(id_to_class_name.get(class_id, "Unknown"))
        wins.append(False)  # These participants are losers
        dates.append(fight_date)
        ids.append(fight_json["id"])

    # Create the DataFrame
    df = pd.DataFrame({"ID": ids, "Class": class_names, "Win": wins, "Date": dates})

    return df


def fetch_ids(driver: WebDriver, url: str, min: int, max: int) -> list[str]:
    # Navigate to the URL with Selenium
    driver.get(url)

    js_code = f"""
    var callback = arguments[0];
    $.getJSON("/hrald/proxy.php?fights/list?min={min}&max={max}", function(data) {{
        callback(data);
    }});
    """
    data = driver.execute_async_script(js_code)  # type: ignore

    ids: list[str] = [
        data[x]["id"] for x in data if isinstance(data[x], dict) and "id" in data[x]  # type: ignore # noqa
    ]

    return ids


async def fetch_details(
    session: aiohttp.ClientSession,
    base_url: str,
    id: str,
    limiter: partial[bool],
    semaphore: asyncio.Semaphore,
    headers: dict[str, str],
) -> dict[str, Any]:
    url = f"{base_url}{id}"

    async def _make_request_with_retries() -> dict[str, Any]:
        retries = 0
        max_retries = 5
        retry_wait = 1  # seconds to wait before retrying
        while retries < max_retries:
            print(f"Fetching data for {id}")
            if not limiter("api_request"):
                await asyncio.sleep(retry_wait)
                continue
            try:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    # Add id to the response
                    response_json["id"] = id
                    return response_json
            except aiohttp.ClientError as e:
                print(f"Failed to fetch data for {id}: {e}")
                retries += 1
                if retries >= max_retries:
                    print(f"Reached max retries for {id}, skipping...")
                    return {
                        "id": id,
                        "error": "Failed to fetch data after multiple attempts",
                    }
                await asyncio.sleep(retry_wait)  # Wait before retrying
                retry_wait *= 2  # Exponential backoff

        return {}

    async with semaphore:
        return await _make_request_with_retries()


async def fetch_all_data(
    base_url: str,
    ids_url: str,
    concurrent_requests: int,
    headers: dict[str, str],
    limiter: partial[bool],
    driver: WebDriver,
    min: int,
    max: int,
    known_ids: set[str] = set(),
    max_details: int | None = None,
    progress_bar: Any | None = None,
) -> list[dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
        all_ids = fetch_ids(driver, ids_url, min, max)

        # Filter out IDs that are already known (i.e., already fetched and stored)
        new_ids = [id for id in all_ids if id not in known_ids]

        if max_details is not None:
            new_ids = new_ids[:max_details]

        total_ids = len(new_ids)

        semaphore = asyncio.Semaphore(concurrent_requests)  # Control concurrency
        tasks = [
            fetch_details(session, base_url, id, limiter, semaphore, headers)
            for id in new_ids
        ]

        results = []
        completed = 0
        # Using as_completed lets us process tasks as they finish.
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            completed += 1
            if progress_bar:
                # Update progress bar using a fraction between 0.0 and 1.0.
                progress_bar.progress(completed / total_ids)

        if progress_bar:
            progress_bar.empty()

        # Handle or log errors as before:
        successful_details = [detail for detail in results if not detail.get("error")]
        return successful_details


def fetch_fight_data(
    driver: WebDriver,
    min: int,
    max: int,
    token: str,
    known_ids: set[str] = set(),
    max_details: int | None = None,
    progress_bar: Any | None = None,
) -> pd.DataFrame:
    # The URL of the API endpoint
    ids_url = "https://eden-daoc.net/fights"
    base_url = "https://eden-daoc.net/fghts/fight.php?"

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",  # noqa
        "X-Herald-Api": "minified",
        "Cookie": f"eden_daoc_sid={token}",
    }

    # Fetch the data
    moving_window = MovingWindowRateLimiter(storage=MemoryStorage())
    one_per_second = RateLimitItemPerSecond(5)
    limiter = partial(moving_window.hit, one_per_second)
    data = asyncio.run(
        fetch_all_data(
            base_url=base_url,
            ids_url=ids_url,
            concurrent_requests=5,
            headers=headers,
            limiter=limiter,
            driver=driver,
            min=min,
            max=max,
            known_ids=known_ids,
            max_details=max_details,
            progress_bar=progress_bar,
        )
    )

    if len(data) == 0:
        return pd.DataFrame()

    # Obtain the class name mapping
    daoc_config = fetch_daoc_config(headers)
    id_to_class_name = create_id_to_class_name_mapping(daoc_config)

    # Extract the fight details
    fight_data = pd.concat(  # type: ignore
        [extract_fight_details(fight_json, id_to_class_name) for fight_json in data]
    )
    fight_data.reset_index(drop=True, inplace=True)

    return fight_data


def cleanup(driver: WebDriver) -> None:
    driver.quit()


if __name__ == "__main__":
    driver = init_driver(headless=False)
    try:
        token = login(driver)
        data = fetch_data(driver, Realm.ALL)
        print(data)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cleanup(driver)
