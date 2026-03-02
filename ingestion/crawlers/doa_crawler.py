"""
DOA Crawler — scrapes doa.gov.lk for agricultural advisory PDFs.
Uses async Playwright with 3-retry exponential backoff.
"""
import asyncio
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from loguru import logger
from playwright.async_api import async_playwright, Page, BrowserContext
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from config.settings import settings

DOA_BASE_URL = "https://www.doa.gov.lk"
DOA_PUBLICATION_PATHS = [
    "/en/advisory",
    "/en/publications",
    "/en/crop-recommendations",
]


def _is_pdf_link(href: str) -> bool:
    return href.lower().endswith(".pdf") or "pdf" in href.lower()


@retry(
    stop=stop_after_attempt(settings.max_crawl_retries),
    wait=wait_exponential(multiplier=settings.crawl_backoff_base, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _fetch_page_links(page: Page, url: str) -> list[str]:
    """Navigate to a URL and return all PDF href links found."""
    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    anchors = await page.query_selector_all("a[href]")
    pdf_links = []
    for anchor in anchors:
        href = await anchor.get_attribute("href") or ""
        if _is_pdf_link(href):
            full_url = urljoin(DOA_BASE_URL, href) if href.startswith("/") else href
            if DOA_BASE_URL in full_url or urlparse(full_url).netloc == "":
                pdf_links.append(full_url)
    return list(set(pdf_links))


@retry(
    stop=stop_after_attempt(settings.max_crawl_retries),
    wait=wait_exponential(multiplier=settings.crawl_backoff_base, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _download_pdf(context: BrowserContext, url: str, dest: Path) -> Path | None:
    """Download a single PDF using a new page and Playwright's download handling."""
    if dest.exists():
        logger.debug(f"Already downloaded: {dest.name}")
        return dest

    page = await context.new_page()
    try:
        async with page.expect_download(timeout=60_000) as download_info:
            await page.goto(url, timeout=60_000)
        download = await download_info.value
        await download.save_as(str(dest))
        logger.info(f"Downloaded: {dest.name} ({url})")
        return dest
    except Exception as exc:
        logger.warning(f"Download failed for {url}: {exc}")
        return None
    finally:
        await page.close()


async def crawl_doa(output_dir: Path | None = None) -> list[Path]:
    """
    Crawl doa.gov.lk and download all advisory PDFs.

    Args:
        output_dir: Destination folder. Defaults to settings.raw_data_dir / "doa".

    Returns:
        List of paths to downloaded PDF files.
    """
    output_dir = output_dir or (settings.raw_data_dir / "doa")
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        all_pdf_urls: list[str] = []
        for path in DOA_PUBLICATION_PATHS:
            url = urljoin(DOA_BASE_URL, path)
            try:
                links = await _fetch_page_links(page, url)
                logger.info(f"Found {len(links)} PDF links at {url}")
                all_pdf_urls.extend(links)
            except Exception as exc:
                logger.error(f"Failed to scrape {url}: {exc}")

        all_pdf_urls = list(set(all_pdf_urls))
        logger.info(f"Total unique PDFs to download: {len(all_pdf_urls)}")

        for pdf_url in all_pdf_urls:
            filename = Path(urlparse(pdf_url).path).name
            # Sanitise filename
            filename = re.sub(r"[^\w\-.]", "_", filename) or "document.pdf"
            dest = output_dir / filename
            result = await _download_pdf(context, pdf_url, dest)
            if result:
                downloaded.append(result)

        await browser.close()

    logger.info(f"DOA crawl complete. {len(downloaded)} PDFs saved to {output_dir}")
    return downloaded


if __name__ == "__main__":
    asyncio.run(crawl_doa())
