#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generuje kanał RSS **lub** JSON (JSON Feed) z działu wiadomości Bankier.pl
– skanowanie pierwszych stron, tylko artykuły z ostatnich 48h.

Obsługiwane sekcje:
  - "news"   -> https://www.bankier.pl/wiadomosc/        (pierwsze 5 stron)
  - "gielda" -> https://www.bankier.pl/gielda/wiadomosci (pierwsza strona)

Użycie (przykłady):
    python bankier_rss.py rss              > docs/bankier-rss.xml
    python bankier_rss.py json             > docs/bankier-feed.json
    python bankier_rss.py rss  gielda      > docs/bankier-gielda-rss.xml
    python bankier_rss.py json gielda      > docs/bankier-gielda-feed.json
"""

import logging
import time
import sys
import json
import re
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

# Sekcja ogólna wiadomości
NEWS_SECTION_URL = "https://www.bankier.pl/wiadomosc/"
NUM_PAGES_NEWS = 5  # ile stron /wiadomosc/, /wiadomosc/2 ... /wiadomosc/5

# Sekcja giełdowa
GIELD_SECTION_URL = "https://www.bankier.pl/gielda/wiadomosci"
NUM_PAGES_GIELDA = 1  # obecnie tylko pierwsza strona (reszta ładowana JS)

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

# 👉 PODMIEŃ NA WŁAŚCIWE URL-e GitHub Pages:
# Przykład:
#   https://twoj-login.github.io/twoj-repo/bankier-feed.json
#   https://twoj-login.github.io/twoj-repo/bankier-gielda-feed.json
FEED_JSON_URL_NEWS = "https://twoj-login.github.io/twoj-repo/bankier-feed.json"
FEED_JSON_URL_GIELDA = "https://twoj-login.github.io/twoj-repo/bankier-gielda-feed.json"

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


# --------------------------------------------------------------------
# PARSOWANIE LISTY ARTYKUŁÓW – SEKCJA /wiadomosc/
# --------------------------------------------------------------------


def parse_article_list(html: str) -> List[Dict]:
    """
    Parsuje HTML pojedynczej strony z listą wiadomości (sekcja /wiadomosc/)
    i zwraca listę dictów: {title, link, pub_date (datetime), teaser}.
    """
    soup = BeautifulSoup(html, "html.parser")

    section = soup.find("section", id="articleList")
    if not section:
        logging.warning("Nie znaleziono sekcji #articleList")
        return []

    articles: List[Dict] = []
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

    logging.info("Znaleziono %d artykułów na stronie (sekcja /wiadomosc/)", len(articles))
    return articles


# --------------------------------------------------------------------
# PARSOWANIE LISTY ARTYKUŁÓW – SEKCJA /gielda/wiadomosci
# --------------------------------------------------------------------


def parse_gielda_list(html: str) -> List[Dict]:
    """
    Parsuje HTML strony https://www.bankier.pl/gielda/wiadomosci.

    Na tej podstronie lista jest renderowana jako linki, których tekst
    zaczyna się od:
        YYYY-MM-DD HH:MM Tytuł...

    Nie ma klasycznego <section id="articleList">, więc chwytamy linki
    regexem po dacie na początku tekstu.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    articles: List[Dict] = []

    # Szukamy <a>, których tekst wygląda jak "2025-12-31 10:00 Coś tam..."
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+(.+)$")

    for a in main.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not text:
            continue

        m = pattern.match(text)
        if not m:
            continue

        dt_str, title = m.groups()

        # Parsujemy datę bez sekund (np. "2025-12-31 10:00")
        try:
            dt_naive = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        except ValueError:
            continue

        pub_dt = TZ_WARSAW.localize(dt_naive)

        rel_link = a["href"]
        link = urljoin(BASE_URL, rel_link)

        articles.append(
            {
                "title": title,
                "link": link,
                "pub_date": pub_dt,
                "teaser": "",  # na liście giełdowej nie ma klasycznej zajawki
            }
        )

    logging.info(
        "Znaleziono %d artykułów na stronie (sekcja /gielda/wiadomosci)",
        len(articles),
    )
    return articles


# --------------------------------------------------------------------
# ZBIERANIE ARTYKUŁÓW Z FILTREM CZASOWYM
# --------------------------------------------------------------------


def collect_recent_articles(section: str = "news") -> List[Dict]:
    """
    Skanuje strony danej sekcji i zwraca artykuły z ostatnich HOURS_BACK godzin.

    section:
      - "news"   -> /wiadomosc/ (+ numer strony)
      - "gielda" -> /gielda/wiadomosci (obecnie tylko pierwsza strona)
    """
    section = section.lower().strip()
    if section not in {"news", "gielda"}:
        raise ValueError(f"Nieznana sekcja: {section!r} (dozwolone: news, gielda)")

    if section == "news":
        base_url = NEWS_SECTION_URL
        num_pages = NUM_PAGES_NEWS
        parser = parse_article_list
    else:  # gielda
        base_url = GIELD_SECTION_URL
        num_pages = NUM_PAGES_GIELDA
        parser = parse_gielda_list

    all_articles: List[Dict] = []
    seen_links = set()

    now = datetime.now(TZ_WARSAW)
    cutoff = now - timedelta(hours=HOURS_BACK)
    logging.info(
        "Sekcja: %s, filtr czasowy: tylko artykuły od %s",
        section,
        cutoff.isoformat(),
    )

    for page in range(1, num_pages + 1):
        if page == 1:
            url = base_url
        else:
            # /wiadomosc/2, /wiadomosc/3, ...
            # (dla giełdy num_pages=1, więc tu nie wchodzimy)
            url = f"{base_url}{page}"

        html = fetch_page_html(url)
        if not html:
            continue

        page_articles = parser(html)

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
    logging.info(
        "Sekcja: %s, łącznie %d artykułów po filtrach", section, len(all_articles)
    )
    return all_articles


# --------------------------------------------------------------------
# GENERATORY: RSS + JSON
# --------------------------------------------------------------------


def generate_rss(
    articles: List[Dict],
    *,
    section_url: str,
    feed_title: str,
) -> bytes:
    """Buduje kanał RSS 2.0 na podstawie listy artykułów i zwraca XML jako bytes."""
    fg = FeedGenerator()
    fg.load_extension("dc")  # opcjonalne, ale bywa przydatne

    fg.title(feed_title)
    fg.link(href=section_url, rel="alternate")
    fg.link(href=section_url, rel="self")
    fg.description(
        f"Automatyczny kanał RSS z Bankier.pl (ostatnie {HOURS_BACK} godzin)"
    )
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


def generate_json_feed(
    articles: List[Dict],
    feed_url: Optional[str],
    *,
    home_url: str,
    feed_title: str,
) -> str:
    """
    Buduje JSON Feed 1.0 (w stylu Inoreader /view/json).
    Zwraca string JSON (unicode).
    """
    feed: Dict = {
        "version": "https://jsonfeed.org/version/1",
        "title": feed_title,
        "home_page_url": home_url,
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
    # domyślnie "rss" + sekcja "news"
    fmt = sys.argv[1].lower() if len(sys.argv) > 1 else "rss"
    section = sys.argv[2].lower() if len(sys.argv) > 2 else "news"

    if section not in {"news", "gielda"}:
        raise SystemExit(
            f"Nieznana sekcja: {section!r}. Użyj: news albo gielda."
        )

    articles = collect_recent_articles(section=section)

    if section == "news":
        section_url = NEWS_SECTION_URL
        feed_title = "Bankier.pl – Najnowsze wiadomości"
        feed_json_url = FEED_JSON_URL_NEWS
    else:
        section_url = GIELD_SECTION_URL
        feed_title = "Bankier.pl – Giełda – Wiadomości"
        feed_json_url = FEED_JSON_URL_GIELDA

    if fmt == "rss":
        rss_bytes = generate_rss(
            articles,
            section_url=section_url,
            feed_title=feed_title,
        )
        print(rss_bytes.decode("utf-8"))
    elif fmt == "json":
        json_str = generate_json_feed(
            articles,
            feed_url=feed_json_url,
            home_url=section_url,
            feed_title=feed_title,
        )
        print(json_str)
    else:
        raise SystemExit(f"Nieznany format: {fmt!r}. Użyj: rss albo json.")


if __name__ == "__main__":
    main()
