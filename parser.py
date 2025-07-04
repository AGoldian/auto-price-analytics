from playwright.sync_api import sync_playwright
import csv
import os
from bs4 import BeautifulSoup

CSV_FILE = "cars.csv"

def extract_price_sale_china(detail_page):
    try:
        html = detail_page.content()
        soup = BeautifulSoup(html, "html.parser")

        block = soup.select_one("div.product-card__characteristics")
        if not block:
            print("    ⚠️ Блок характеристик не найден")
            return ""

        text = block.get_text().splitlines()
        text = [x for x in text if x]
        for line_num in range(len(text)):
            if "Цена продажи" in text[line_num]:
                price = text[line_num + 1]
                print(f"    💴 Найдена цена в Китае: {price}")
                return price

        print("    ⚠️ Цена в Китае не найдена")
        return ""
    except Exception as e:
        print(f"  ❌ Ошибка при получении цены в Китае: {e}")
        return ""

def save_row(fieldnames, row, first_write=False):
    mode = "w" if first_write else "a"
    with open(CSV_FILE, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if first_write:
            writer.writeheader()
        writer.writerow(row)

def parse_all_pages(context, page, max_pages=5):
    first_write = not os.path.exists(CSV_FILE)
    seen_fields = set()
    #https://japautobuy.ru/avtomobili-iz-kitaya?current_page=2
    #https://japautobuy.ru/avtomobili-iz-kitaya?market=china&is_europe=0&current_page=2&per_page=16&order_by=popularity_score&sort=desc

    for page_num in range(1, max_pages + 1):
        url = f"https://japautobuy.ru/avtomobili-iz-kitaya?market=china&is_europe=0&current_page={page_num}&per_page=16&order_by=popularity_score&sort=desc"
        print(f"\n📄 Загружаем страницу {page_num}: {url}")
        page.goto(url, timeout=60000)
        try:
            page.wait_for_selector("article.car-card", timeout=15000)
        except:
            print("⚠️ Не удалось найти карточки автомобилей — возможно, это последняя страница.")
            break

        cards = page.query_selector_all("article.car-card")
        if not cards:
            print("📌 Карточки не найдены. Завершено.")
            break

        for idx, card in enumerate(cards):
            print(f"\n🚗 Машина {idx + 1}/{len(cards)} (стр. {page_num})")

            title_el = card.query_selector("h2")
            price_el = card.query_selector(".car-card__cost-item-key")
            link_el = card.query_selector("a[href*='/auto/']")

            title = title_el.inner_text().strip() if title_el else "N/A"
            price = price_el.inner_text().strip() if price_el else "N/A"
            href = link_el.get_attribute("href") if link_el else None

            print(f"  Название: {title}")
            print(f"  Цена: {price}")

            specs = {}
            for li in card.query_selector_all("ul li"):
                txt = li.inner_text()
                if ":" in txt:
                    key, val = txt.split(":", 1)
                    specs[key.strip()] = val.strip()

            sale_price_china = ""
            if href:
                detail_url = href if href.startswith("http") else f"https://japautobuy.ru{href}"
                try:
                    detail_page = context.new_page()
                    detail_page.goto(detail_url, timeout=60000)
                    detail_page.wait_for_timeout(2000)
                    sale_price_china = extract_price_sale_china(detail_page)
                    detail_page.close()
                except Exception as e:
                    print(f"  ❌ Ошибка при переходе: {e}")

            row = {
                "title": title,
                "price": price,
                "url": href,
                **specs,
                "price_sale_china": sale_price_china
            }

            all_keys = sorted(set(row.keys()).union(seen_fields))
            seen_fields.update(all_keys)
            save_row(all_keys, row, first_write=first_write)
            first_write = False




def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://japautobuy.ru/avtomobili-iz-kitaya", timeout=60000)
        parse_all_pages(context, page, max_pages=3)

        browser.close()

    print(f"\n✅ Сбор данных завершён. Файл: {CSV_FILE}")

if __name__ == "__main__":
    main()
