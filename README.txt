Bankier.pl – Automatyczny kanał RSS + JSON Feed

Ten projekt generuje automatyczny kanał RSS oraz JSON Feed z działu „Wiadomości” serwisu Bankier.pl
👉 https://www.bankier.pl/wiadomosc/

Skrypt w Pythonie:

pobiera nagłówki wiadomości z pierwszych 5 stron działu

wyciąga tytuł, link, datę (publikacji/aktualizacji) oraz zajawkę

filtruje newsy do ostatnich 48 godzin

generuje:

RSS 2.0 (biblioteka feedgen)

JSON Feed 1.0 (kompatybilny ze stylem Inoreader /view/json)

uruchamiany jest automatycznie przez GitHub Actions

wynik publikowany jest przez GitHub Pages jako statyczne pliki

🔗 Adresy feedów
RSS
https://bbttoonnee-commits.github.io/rrs_json/bankier-rss.xml

JSON Feed
https://bbttoonnee-commits.github.io/rrs_json/bankier-feed.json

📁 Struktura projektu
.
├── bankier_rss.py              # Skrypt generujący RSS i JSON
├── requirements.txt
├── docs/
│   ├── bankier-rss.xml         # Wygenerowany RSS
│   └── bankier-feed.json       # Wygenerowany JSON Feed
└── .github/
    └── workflows/
        └── bankier-rss.yml     # Workflow GitHub Actions

⚙️ Jak działa skrypt

Pobiera HTML z:

https://www.bankier.pl/wiadomosc/

https://www.bankier.pl/wiadomosc/2

… do 5 strony

Z listy artykułów wyciąga:

tytuł

pełny link

datę (publikacji lub aktualizacji – używana jest nowsza)

zajawkę (bez „Czytaj dalej”)

Konwertuje czas do Europe/Warsaw

Filtrowane są artykuły z ostatnich 48h

Tworzone są dwa feedy:

RSS 2.0

GUID = pełny URL artykułu

opis = zajawka

pubDate = data ze strefą TZ

JSON Feed 1.0

Każdy wpis zawiera m.in.:

{
  "id": "<URL>",
  "url": "<URL>",
  "title": "Tytuł",
  "content_html": "Zajawka",
  "date_published": "2025-12-30T21:09:00+01:00"
}


Workflow zapisuje pliki do:

docs/bankier-rss.xml
docs/bankier-feed.json

🔧 Konfiguracja

W bankier_rss.py możesz zmienić:

NUM_PAGES = 5
HOURS_BACK = 48
SLEEP_BETWEEN_REQUESTS = 2.5


np.:

HOURS_BACK = 72
NUM_PAGES = 3


Nagłówki HTTP ustawisz w HEADERS.

▶️ Ręczne uruchomienie

Instalacja zależności:

pip install requests beautifulsoup4 feedgen pytz


lub

pip install -r requirements.txt


Generowanie RSS:

python bankier_rss.py rss > docs/bankier-rss.xml


Generowanie JSON Feed:

python bankier_rss.py json > docs/bankier-feed.json

🤖 GitHub Actions

Workflow:

.github/workflows/bankier-rss.yml


Uruchamia się:

co 30 minut

lub ręcznie

Commit jest tworzony tylko gdy pliki się zmienią.

🌐 GitHub Pages

Ustaw w repozytorium:

Settings → Pages

Source: Deploy from a branch

Branch: main

Folder: /docs

Feed RSS dostępny pod:

https://bbttoonnee-commits.github.io/rrs_json/bankier-rss.xml


Feed JSON pod:

https://bbttoonnee-commits.github.io/rrs_json/bankier-feed.json

🛠 Troubleshooting

Brak pliku RSS/JSON

sprawdź logi Actions

upewnij się, że commit się wykonał

Brak nowych artykułów

działa filtr ostatnich 48h

zmień HOURS_BACK

Za dużo requestów

zwiększ SLEEP_BETWEEN_REQUESTS

🚀 Pomysły na rozwój

parametryzacja przez zmienne środowiskowe

pełne pobieranie treści artykułu

cache HTTP

walidacja XML/JSON w workflow

paginacja JSON Feed

webhook / Telegram bot

🧩 Technologie

Python

GitHub Actions

GitHub Pages

➡️ bez własnego serwera, w pełni serverless
