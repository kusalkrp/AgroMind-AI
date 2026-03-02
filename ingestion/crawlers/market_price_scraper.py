"""
Market Price Scraper — scrapes agriculture.gov.lk weekly wholesale price HTML tables.
Writes results to CSV in data/raw/market/.
"""
import asyncio
import csv
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from config.settings import settings

MARKET_BASE_URL = "https://www.agriculture.gov.lk"
MARKET_PRICE_PATHS = [
    "/web/index.php/en/market-information/wholesale-prices",
    "/web/index.php/en/market-information/retail-prices",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AgroMindBot/1.0; +https://agromind.ai/bot)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@retry(
    stop=stop_after_attempt(settings.max_crawl_retries),
    wait=wait_exponential(multiplier=settings.crawl_backoff_base, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url, follow_redirects=True, timeout=30.0)
    response.raise_for_status()
    return response.text


def _parse_price_table(html: str, source_url: str) -> list[dict]:
    """Parse HTML tables containing market price data."""
    soup = BeautifulSoup(html, "lxml")
    records = []
    scraped_date = datetime.utcnow().strftime("%Y-%m-%d")

    for table in soup.find_all("table"):
        headers_row = table.find("tr")
        if not headers_row:
            continue

        col_headers = [
            th.get_text(strip=True).lower()
            for th in headers_row.find_all(["th", "td"])
        ]

        # Heuristic: look for tables with commodity/price columns
        has_commodity = any("commodity" in h or "crop" in h or "item" in h for h in col_headers)
        has_price = any("price" in h or "rate" in h or "value" in h for h in col_headers)
        if not (has_commodity and has_price):
            continue

        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 2:
                continue
            record = {
                "scraped_date": scraped_date,
                "source_url": source_url,
            }
            for i, header in enumerate(col_headers):
                if i < len(cells):
                    record[header] = cells[i]
            records.append(record)

    return records


def _write_csv(records: list[dict], output_path: Path) -> None:
    if not records:
        logger.warning(f"No records to write to {output_path}")
        return
    fieldnames = list(records[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    logger.info(f"Wrote {len(records)} price records to {output_path}")


async def scrape_market_prices(output_dir: Path | None = None) -> list[Path]:
    """
    Scrape weekly market price tables from agriculture.gov.lk.

    Args:
        output_dir: Destination folder. Defaults to settings.raw_data_dir / "market".

    Returns:
        List of CSV file paths written.
    """
    output_dir = output_dir or (settings.raw_data_dir / "market")
    output_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []
    date_tag = datetime.utcnow().strftime("%Y%m%d")

    async with httpx.AsyncClient(headers=HEADERS) as client:
        for path in MARKET_PRICE_PATHS:
            url = urljoin(MARKET_BASE_URL, path)
            price_type = "wholesale" if "wholesale" in path else "retail"
            try:
                html = await _fetch_html(client, url)
                records = _parse_price_table(html, source_url=url)
                if records:
                    filename = f"market_{price_type}_{date_tag}.csv"
                    output_path = output_dir / filename
                    _write_csv(records, output_path)
                    written_files.append(output_path)
                else:
                    logger.warning(f"No price table found at {url}")
            except Exception as exc:
                logger.error(f"Failed to scrape market prices from {url}: {exc}")

    logger.info(f"Market price scrape complete. Files: {[f.name for f in written_files]}")
    return written_files


if __name__ == "__main__":
    asyncio.run(scrape_market_prices())
