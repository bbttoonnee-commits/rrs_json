#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje kanał RSS **lub** JSON (JSON Feed) z działu wiadomości Bankier.pl
– skanowanie pierwszych 5 stron, tylko artykuły z ostatnich 48h.

Użycie:
    python bankier_rss.py rss   > docs/bankier-rss.xml
    python bankier_rss.py json  > docs/bankier-feed.json
"""

import logging
import time
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin

import pytz
import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# --------------------------------------------------------------------
# KONFIGURACJA
# --------------------------------------------------------------------

BASE_URL = "https://www.bankier.pl"
NEWS_SECTION_URL = "https://www.bankier.pl/wiadomosc/"
NUM_PAGES = 5  # ile stron /wiadomosc/, /wiadomosc/2 ... /wiadomosc/5
SLEEP_BETWEEN_REQUESTS = 2.5  # sekundy
HOURS_BACK = 48  # filtr czasu – ostatnie 48 godzin

TZ_WARSAW = pytz.timezone("Europe/Warsaw")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.bankier.pl/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "close",
}

# 👉 PODMIEŃ NA WŁAŚCIWY URL GitHub Pages:
# Przykład: https://twoj-login.github.io/twoj-repo/bankier-feed.json
FEED_JSON_URL = "https://twoj-login.github.io/twoj-repo/bankier-feed.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# --------------------------------------------------------------------
# FUNKCJE POMOCNICZE
# --------------------------------------------------------------------


def fetch_page_html(url: str) -> Optional[str]:
    """Pobiera HTML strony, zwraca tekst lub None w razie błędu."""
    logging.info("Pobieram stronę: %s", url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        logging.error("Błąd pobierania %s: %s", url, exc)
        return None
    finally:
        # mały sleep, żeby nie spamować serwera
        time.sleep(SLEEP_BETWEEN_REQUESTS)


def parse_article_list(html: str) -> List[Dict]:
    """
    Parsuje HTML pojedynczej strony z listą wiadomości
    i zwraca listę dictów: {title, link, pub_date (datetime), teaser}.
    """
    soup = BeautifulSoup(html, "html.parser")

    section = soup.find("section", id="articleList")
    if not section:
        logging.warning("Nie znaleziono sekcji #articleList")
        return []

    articles = []
    # każdy artykuł siedzi w <div class="article">
    for art in section.find_all("div", class_="article", recursive=False):
        try:
            content = art.find("div", class_="entry-content")
            if not content:
                continue

            # --- tytuł + link ---
            title_span = content.find("span", class_="entry-title")
            if not title_span:
                continue
            a_tag = title_span.find("a")
            if not a_tag or not a_tag.get("href"):
                continue

            title = " ".join(a_tag.get_text(strip=True).split())
            rel_link = a_tag["href"]
            link = urljoin(BASE_URL, rel_link)

            # --- data publikacji / aktualizacji ---
            meta_div = content.find("div", class_="entry-meta")
            if not meta_div:
                continue

            time_tags = meta_div.find_all("time", class_="entry-date")
            if not time_tags:
                continue

            # bierzemy ostatni <time> (zwykle aktualizacja, jeśli jest)
            dt_str = time_tags[-1].get("datetime") or time_tags[-1].get_text(
                strip=True
            )
            if not dt_str:
                continue

            # Bankier używa ISO-8601 z offsetem np. 2025-12-29T21:09:00+01:00
            pub_dt = datetime.fromisoformat(dt_str)
            if pub_dt.tzinfo is None:
                # awaryjnie, gdyby brakowało strefy
                pub_dt = TZ_WARSAW.localize(pub_dt)
            else:
                pub_dt = pub_dt.astimezone(TZ_WARSAW)

            # --- zajawka ---
            teaser_tag = content.find("p")
            teaser = ""
            if teaser_tag:
                # usuń link "Czytaj dalej"
                for more_link in teaser_tag.find_all("a", class_="more-link"):
                    more_link.decompose()
                teaser = " ".join(
                    teaser_tag.get_text(" ", strip=True).split()
                )

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "pub_date": pub_dt,
                    "teaser": teaser,
                }
            )
        except Exception as exc:
            logging.warning("Błąd parsowania pojedynczego artykułu: %s", exc)
            continue

    logging.info("Znaleziono %d artykułów na stronie", len(articles))
    return articles


def collect_recent_articles() -> List[Dict]:
    """Skanuje pierwsze NUM_PAGES stron i zwraca artykuły z ostatnich HOURS_BACK godzin."""
    all_articles: List[Dict] = []
    seen_links = set()

    now = datetime.now(TZ_WARSAW)
    cutoff = now - timedelta(hours=HOURS_BACK)
    logging.info("Filtr czasowy: tylko artykuły od %s", cutoff.isoformat())

    for page in range(1, NUM_PAGES + 1):
        if page == 1:
            url = NEWS_SECTION_URL
        else:
            url = f"{NEWS_SECTION_URL}{page}"

        html = fetch_page_html(url)
        if not html:
            continue

        page_articles = parse_article_list(html)

        for art in page_articles:
            link = art["link"]

            # deduplikacja po URL
            if link in seen_links:
                continue

            # filtr po dacie
            if art["pub_date"] < cutoff:
                continue

            seen_links.add(link)
            all_articles.append(art)

    # sortujemy malejąco po dacie
    all_articles.sort(key=lambda x: x["pub_date"], reverse=True)
    logging.info("Łącznie %d artykułów po filtrach", len(all_articles))
    return all_articles


# --------------------------------------------------------------------
# GENERATORY: RSS + JSON
# --------------------------------------------------------------------


def generate_rss(articles: List[Dict]) -> bytes:
    """Buduje kanał RSS 2.0 na podstawie listy artykułów i zwraca XML jako bytes."""
    fg = FeedGenerator()
    fg.load_extension("dc")  # opcjonalne, ale bywa przydatne

    fg.title("Bankier.pl – Najnowsze wiadomości")
    fg.link(href=NEWS_SECTION_URL, rel="alternate")
    fg.link(href=NEWS_SECTION_URL, rel="self")
    fg.description(f"Automatyczny kanał RSS z Bankier.pl (ostatnie {HOURS_BACK} godzin)")
    fg.language("pl")

    if articles:
        # lastBuildDate = najnowszy artykuł
        fg.lastBuildDate(articles[0]["pub_date"])

    for art in articles:
        fe = fg.add_entry()
        fe.id(art["link"])  # GUID oparty na URL
        fe.link(href=art["link"])
        fe.title(art["title"])
        if art["teaser"]:
            fe.description(art["teaser"])
        fe.pubDate(art["pub_date"])

    # pretty=True dla czytelności, można ustawić False
    return fg.rss_str(pretty=True)


def generate_json_feed(articles: List[Dict], feed_url: Optional[str] = None) -> str:
    """
    Buduje JSON Feed 1.0 (w stylu Inoreader /view/json).
    Zwraca string JSON (unicode).
    """
    feed: Dict = {
        "version": "https://jsonfeed.org/version/1",
        "title": "Bankier.pl – Najnowsze wiadomości",
        "home_page_url": NEWS_SECTION_URL,
        "description": f"Automatyczny kanał JSON z Bankier.pl (ostatnie {HOURS_BACK} godzin)",
        "items": [],
    }

    if feed_url:
        feed["feed_url"] = feed_url

    items = []
    for art in articles:
        item = {
            "id": art["link"],
            "url": art["link"],
            "title": art["title"],
            # teaser jako content_html – możesz później rozbudować o pełną treść
            "content_html": art["teaser"],
            # ISO-8601 z informacją o strefie czasowej
            "date_published": art["pub_date"].isoformat(),
        }
        items.append(item)

    feed["items"] = items

    # ensure_ascii=False żeby polskie znaki były normalne, nie \u0144 itd.
    return json.dumps(feed, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------


def main() -> None:
    # domyślnie "rss", ale można podać "json"
    fmt = sys.argv[1].lower() if len(sys.argv) > 1 else "rss"

    articles = collect_recent_articles()

    if fmt == "rss":
        rss_bytes = generate_rss(articles)
        print(rss_bytes.decode("utf-8"))
    elif fmt == "json":
        json_str = generate_json_feed(articles, feed_url=FEED_JSON_URL)
        print(json_str)
    else:
        raise SystemExit(f"Nieznany format: {fmt!r}. Użyj: rss albo json.")


if __name__ == "__main__":
    main()
