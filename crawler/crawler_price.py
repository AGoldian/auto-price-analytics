import os
import sys
import time
import argparse
import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from models.llm_price import estimate_price

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("crawler_price")


def extract_make_model(url: str) -> tuple[str, str]:
    path = PurePosixPath(urlparse(url).path)
    parts = [p.lower() for p in path.parts if p.isalpha()]
    return (parts[0], parts[1]) if len(parts) >= 2 else ("", "")


def grab_characteristics(url: str) -> str:
    """Возвращает текст секции «Характеристики» или всего body."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_navigation_timeout(60000)

        logger.info("▶Навигация к %s", url)
        t0 = time.time()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            logger.info("  – Загружено за %.2f сек", time.time() - t0)
        except PlaywrightTimeoutError:
            logger.warning("  – Навигация превысила таймаут")

        try:
            page.wait_for_selector("h2:has-text('Характеристики')", timeout=5000)
            section = page.locator("h2:has-text('Характеристики')")\
                          .locator("xpath=following-sibling::*[1]")
            text = section.inner_text().strip()
            logger.info("▶️  Секция «Характеристики» извлечена (%d симв.)", len(text))
        except Exception:
            text = page.inner_text("body").strip()
            logger.warning("⚠️  Секция не найдена — взят весь body (%d симв.)", len(text))

        browser.close()
    return text


def main():
    parser = argparse.ArgumentParser(description="Краулер + LLM-оценщик (только цена)")
    parser.add_argument("url", help="URL объявления")
    parser.add_argument("--max-chars", type=int, default=1000,
                        help="сколько символов характеристик передавать в LLM")
    parser.add_argument("--model", default="mediocredev/open-llama-3b-v2-instruct",
                        help="имя модели на локальном inference-сервере")
    parser.add_argument("--debug", action="store_true",
                        help="показать trimmed-характеристики перед LLM")
    args = parser.parse_args()

    make, model = extract_make_model(args.url)
    logger.info("make/model: %s %s", make, model)

    raw = grab_characteristics(args.url)
    trimmed = raw[:args.max_chars]

    if args.debug:
        print("\n CHARACTERISTICS (trimmed):\n", trimmed, "\n")

    try:
        price = estimate_price(
            raw_lines=trimmed,
            make=make,
            model=model,
            model_name=args.model,
            max_chars=args.max_chars
        )
    except Exception:
        logger.exception("Ошибка при запросе к LLM")
        sys.exit(1)

    print(price)


if __name__ == "__main__":
    main()
