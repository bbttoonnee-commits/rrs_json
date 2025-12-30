
Bankier.pl – Automatyczny kanał RSS

Ten projekt generuje automatyczny kanał RSS z działu „Wiadomości” serwisu Bankier.pl (https://www.bankier.pl/wiadomosc/).

Skrypt w Pythonie:
- pobiera nagłówki wiadomości z pierwszych 5 stron działu,
- wyciąga tytuł, link, datę (publikacji/aktualizacji) oraz zajawkę,
- filtruje newsy do ostatnich 48 godzin,
- generuje poprawny kanał RSS 2.0 z wykorzystaniem biblioteki feedgen,
- może być uruchamiany automatycznie przez GitHub Actions,
- publikowany jest przez GitHub Pages jako statyczny plik XML.

Docelowa ścieżka RSS:
docs/bankier-rss.xml

Adres RSS przy GitHub Pages:
https://<username>.github.io/<repo>/bankier-rss.xml


STRUKTURA PROJEKTU

.
├── bankier_rss.py              # Główny skrypt generujący kanał RSS
├── requirements.txt            # (opcjonalnie) lista zależności Pythona
├── docs/
│   └── bankier-rss.xml         # Wygenerowany plik RSS (commitowany przez Actions)
└── .github/
    └── workflows/
        └── bankier-rss.yml     # Workflow GitHub Actions


JAK DZIAŁA SKRYPT

1. Pobiera HTML z sekcji wiadomości:
   - https://www.bankier.pl/wiadomosc/
   - https://www.bankier.pl/wiadomosc/2
   - …do 5 strony

2. Wydobywa z listy artykułów:
   - tytuł
   - pełny link
   - datę (publikacji lub aktualizacji – jeżeli są dwie, używana jest nowsza)
   - zajawkę (bez linku „Czytaj dalej”)

3. Konwertuje czas do strefy Europe/Warsaw

4. Filtrowane są artykuły młodsze niż 48 godzin

5. Tworzony jest kanał RSS 2.0 przy użyciu feedgen:
   - GUID = pełny URL artykułu
   - opis = zajawka
   - pubDate = czas ze strefą czasową

6. Skrypt wypisuje XML na stdout, a workflow zapisuje go do docs/bankier-rss.xml


KONFIGURACJA

W pliku bankier_rss.py możesz zmienić:

NUM_PAGES = 5              # liczba stron do zeskanowania
HOURS_BACK = 48            # filtr czasu
SLEEP_BETWEEN_REQUESTS = 2.5  # opóźnienie między zapytaniami w sekundach

Możesz np. ustawić:
HOURS_BACK = 72
NUM_PAGES = 3
SLEEP_BETWEEN_REQUESTS = 1.0

Nagłówki HTTP możesz dopasować w HEADERS:
- User-Agent
- Accept-Language
- Referer


RĘCZNE URUCHOMIENIE

Instalacja zależności:
pip install requests beautifulsoup4 feedgen pytz
lub
pip install -r requirements.txt

Generowanie RSS:
python bankier_rss.py > docs/bankier-rss.xml


GITHUB ACTIONS

Workflow znajduje się w:
.github/workflows/bankier-rss.yml

Uruchamia się:
- co 30 minut
- lub ręcznie z zakładki Actions

Commit wykonywany jest tylko gdy RSS faktycznie się zmieni.


GITHUB PAGES

Ustaw w repozytorium:
Settings → Pages
Source: Deploy from a branch
Branch: main
Folder: /docs

RSS dostępny pod:
https://<username>.github.io/<repo>/bankier-rss.xml


TROUBLESHOOTING

Brak pliku bankier-rss.xml:
- sprawdź logi Actions
- upewnij się, że commit został wykonany

Brak nowych artykułów w RSS:
- pamiętaj że używany jest filtr ostatnich 48 godzin
- możesz zmienić HOURS_BACK lub częstotliwość cron


POMYSŁY NA ROZWÓJ

- parametryzacja przez zmienne środowiskowe
- cache zapytań HTTP
- dodatkowy JSON feed
- weryfikacja poprawności XML w workflow


Projekt wykorzystuje:
- Python
- GitHub Actions
- GitHub Pages

i nie wymaga własnego serwera.
