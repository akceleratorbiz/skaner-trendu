# Skaner trendu – rozwinięty świat (GitHub Actions + Yahoo)

Codziennie po sesji w USA skanuje ok. **10 tys. największych spółek z 26 rynków rozwiniętych + GPW**, osobno dla 8 regionów, i składa wyniki w jeden arkusz zbiorczy z najlepszymi spółkami.

Wynik po każdym przebiegu (folder `results/`):
- **`TOP.md`** – podgląd na telefonie (otwórz w aplikacji GitHub): klimat rynku, TOP 30, Zapłon
- **`SKANER_GLOBALNY.xlsx`** – TOP 100 globalnie, Zapłon, Rozpęd, TOP 15 z każdego regionu, Klimat rynku, Backtest, Metodyka
- **`regiony/<region>.xlsx`** – arkusz regionu: Kandydaci, pełny Ranking, Klimat rynku, Backtest
- `historia/top_RRRR-MM-DD.csv` – TOP 30 z każdego dnia (do śledzenia zmian)
- opcjonalnie: te same zakładki w **Google Sheets**

## Regiony

| Kod | Region | Giełdy (kody Yahoo) | Spółek |
|---|---|---|---|
| `us` | USA | NMS, NYQ, NGM, NCM, ASE | 3000 |
| `ca` | Kanada | TOR, VAN | 800 |
| `uk` | Wielka Brytania | LSE | 800 |
| `eu` | Europa kontynentalna | GER, PAR, MIL, EBS, AMS, MCE, BRU, VIE, LIS, ISE | 1860 |
| `nordic` | Skandynawia | STO, OSL, CPH, HEL | 840 |
| `jp` | Japonia | JPX | 2000 |
| `apac` | Azja-Pacyfik + Izrael | ASX, HKG, KSC, SES, TLV, NZE | 2580 |
| `pl` | Polska | WSE | 400 |

Liczba spółek = największe wg kapitalizacji; zmienisz w `screener/config.py` (`REGIONS → top`).

## Jak to działa

1. **Lista spółek** – wyszukiwarka Yahoo, osobno dla każdego kraju (zapytania po 250). Odświeżana raz w tygodniu i zapisywana w `data/universe/`.
2. **Fundamenty dla całego regionu bez pobierania danych spółka po spółce** – 4 dodatkowe zapytania do wyszukiwarki na każdy kraj: marża netto > 0, wzrost przychodów > 0, ROE ≥ 15%, 0 < P/S ≤ 10. Każda spółka dostaje flagi 0/1, a z nich 0–100 pkt.
3. **Notowania** – 3 lata danych dziennych, pobierane zbiorczo po 100 tickerów, z ponowieniami przy błędach Yahoo.
4. **Metoda** – fazy (Zapłon / Rozpęd / Trend dojrzały / Przegrzanie / Osłabienie), wiek trendu, WST z kwartału i WST 21s, „rośnie codziennie”, RSI, obsunięcie.
5. **Płynność** – średni obrót z 50 sesji przeliczony na USD (≥ 1 mln USD; GPW ≥ 150 tys. USD). Ceny w pensach i agorach są przeliczane automatycznie.
6. **Szczegóły fundamentów** (P/S, P/E, ROE, marże) – pobierane tylko dla 40 najlepszych kandydatów każdego regionu.
7. **Agregacja** – jeden arkusz ze wszystkich regionów. Jeśli któryś region się nie pobierze, arkusz powstaje z pozostałych, a brakujący region jest wyraźnie oznaczony.

## Uruchomienie na GitHubie (jednorazowo, ok. 10 min)

1. Utwórz **publiczne** repozytorium (np. `skaner-trendu`) i wgraj do niego zawartość tego folderu.
2. **Settings → Actions → General → Workflow permissions → „Read and write permissions”** → Save. Bez tego bot nie zapisze wyników.
3. **Actions → „Skaner trendu – rozwinięty świat” → Run workflow**. Pierwszy przebieg najlepiej zrobić dla jednego regionu: wpisz `pl`. Potem uruchom dla wszystkich.
4. Dalej skaner działa sam: **pn–pt o 22:17 UTC** (23:17 lub 00:17 czasu polskiego).

### Google Sheets (opcjonalnie)
1. Google Cloud Console → nowy projekt → włącz **Google Sheets API** → utwórz **konto serwisowe** → pobierz klucz JSON.
2. Utwórz pusty arkusz Google i udostępnij go (Edytor) adresowi e-mail konta serwisowego.
3. W repozytorium: **Settings → Secrets and variables → Actions**: `GOOGLE_SA_JSON` = cała treść pliku JSON, `SHEET_ID` = identyfikator z adresu arkusza.
Zakładki: TOP, Zapłon, Rozpęd, Klimat rynku oraz „R: <region>” (300 najlepszych płynnych spółek).

## Lokalnie
```
pip install -r requirements.txt
python run_region.py --region pl          # jeden region
python run_region.py --region pl --demo   # test bez internetu
python aggregate.py                        # arkusz zbiorczy z output/
```

## Publiczne repozytorium – co warto wiedzieć
- Minuty GitHub Actions w repozytorium publicznym są **darmowe i bez limitu** (standardowe maszyny). Do 20 zadań równolegle, jedno zadanie może trwać najwyżej 6 godzin.
- **Kod i wyniki są publiczne.** Klucze trzymaj wyłącznie w Secrets, nigdy w plikach.
- GitHub wyłącza harmonogram w repozytorium publicznym po 60 dniach bez aktywności. Tu bot codziennie zapisuje wyniki, więc repozytorium stale jest aktywne.
- Uruchomienia według harmonogramu bywają opóźnione o 5–30 minut przy dużym obciążeniu GitHuba.
- Każdy region działa na osobnej maszynie (zwykle z innym IP), najwyżej 4 naraz. To zmniejsza ryzyko blokady przez Yahoo.

## Ograniczenia
- Yahoo to nieoficjalne źródło: może zmienić interfejs, ograniczyć liczbę zapytań lub zwrócić dziury w danych.
- Po pierwszym przebiegu sprawdź w logu udział spółek z ROE ≥ 15%. Jeśli wynosi ok. 0% lub 100%, Yahoo podaje ROE w innych jednostkach: zmień `roe_min_pct` w `screener/config.py`.
- Backtest liczy zwroty bez kosztów transakcyjnych, na dzisiejszej liście spółek (survivorship bias) i ok. 1,5 roku historii. Traktuj go orientacyjnie.
- Materiał analityczny, nie rekomendacja inwestycyjna.
