# -*- coding: utf-8 -*-
"""Parametry metody i definicja regionów. Wszystko, co się stroi, jest tutaj."""

CFG = {
    # ── średnie i okna ──
    "sma_short": 20,
    "sma_mid": 50,
    "sma_long": 200,
    "window": 63,            # okno weryfikacji = kwartał sesyjny
    "window_short": 21,      # krótki WST – ocena samego startu
    # ── fazy ──
    "ignition_max": 10,      # Zapłon: przecięcie SMA20>SMA50 nie starsze niż N sesji
    "momentum_max": 40,      # Rozpęd: przecięcie nie starsze niż N sesji
    "overheat_dist": 0.25,   # Przegrzanie: kurs > SMA50 o ponad 25%
    "rsi_overheat": 75,      # … lub RSI14 > 75
    "er_full": 0.40,         # Efficiency Ratio uznawany za „pełny” w WST
    # ── fundamenty (filtry wyszukiwarki Yahoo, liczone dla całego regionu) ──
    "roe_min_pct": 15,       # ROE ≥ 15 (Yahoo podaje w %)
    "ps_max": 10.0,          # 0 < P/S ≤ 10
    # ── płynność ──
    "min_price_usd": 1.0,
    "min_turnover_usd": 1_000_000,   # średni obrót 50 sesji (cena × wolumen) w USD
    # ── ocena ──
    "w_wst": 0.6,
    "w_fund": 0.4,
    # ── dane ──
    "price_years": 3,        # historia notowań (SMA200 + kwartał + ~1,5 roku backtestu)
    "chunk": 100,            # tickerów na jedno zapytanie zbiorcze o notowania
    "chunk_pause_s": 2.0,
    "universe_max_age_days": 7,   # lista spółek i flagi fundamentów odświeżane raz w tygodniu
    "info_top_n": 40,        # dla ilu najlepszych spółek regionu pobrać pełne liczby fundamentów
    "info_pause_s": 1.2,
    "fwd": (5, 20, 63),      # horyzonty backtestu (sesje)
}

# Kody giełd Yahoo zweryfikowane z yfinance (EQUITY_SCREENER_EQ_MAP).
# "top" = ile największych spółek (wg kapitalizacji) brać z danego kraju.
REGIONS = {
    "us": {
        "name": "USA",
        "countries": {"us": {"exchanges": ["NMS", "NYQ", "NGM", "NCM", "ASE"], "top": 3000}},
    },
    "ca": {
        "name": "Kanada",
        "countries": {"ca": {"exchanges": ["TOR", "VAN"], "top": 800}},
    },
    "uk": {
        "name": "Wielka Brytania",
        "countries": {"gb": {"exchanges": ["LSE"], "top": 800}},
    },
    "eu": {
        "name": "Europa kontynentalna",
        "countries": {
            "de": {"exchanges": ["GER"], "top": 500},
            "fr": {"exchanges": ["PAR"], "top": 400},
            "it": {"exchanges": ["MIL"], "top": 300},
            "ch": {"exchanges": ["EBS"], "top": 200},
            "nl": {"exchanges": ["AMS"], "top": 120},
            "es": {"exchanges": ["MCE"], "top": 120},
            "be": {"exchanges": ["BRU"], "top": 100},
            "at": {"exchanges": ["VIE"], "top": 50},
            "pt": {"exchanges": ["LIS"], "top": 40},
            "ie": {"exchanges": ["ISE"], "top": 30},
        },
    },
    "nordic": {
        "name": "Skandynawia",
        "countries": {
            "se": {"exchanges": ["STO"], "top": 400},
            "no": {"exchanges": ["OSL"], "top": 200},
            "dk": {"exchanges": ["CPH"], "top": 120},
            "fi": {"exchanges": ["HEL"], "top": 120},
        },
    },
    "jp": {
        "name": "Japonia",
        "countries": {"jp": {"exchanges": ["JPX"], "top": 2000}},
    },
    "apac": {
        "name": "Azja-Pacyfik + Izrael",
        "countries": {
            "au": {"exchanges": ["ASX"], "top": 1000},
            "hk": {"exchanges": ["HKG"], "top": 700},
            "kr": {"exchanges": ["KSC"], "top": 400},
            "sg": {"exchanges": ["SES"], "top": 200},
            "il": {"exchanges": ["TLV"], "top": 200},
            "nz": {"exchanges": ["NZE"], "top": 80},
        },
    },
    "pl": {
        "name": "Polska",
        "countries": {"pl": {"exchanges": ["WSE"], "top": 400}},
        "min_turnover_usd": 150_000,   # GPW: niższy próg płynności
    },
}

# Waluty kwotowane w setnych częściach (LSE w pensach, TASE w agorach, JSE w centach)
MINOR_CURRENCIES = {"GBp": ("GBP", 100), "GBX": ("GBP", 100), "ILA": ("ILS", 100), "ZAc": ("ZAR", 100)}

PHASES = {
    "0 Brak trendu": "SMA krótka ≤ SMA średnia",
    "1 Zapłon": "świeże przecięcie SMA krótka > SMA średnia (≤ ignition_max sesji), kurs nad SMA krótką",
    "2 Rozpęd": "przecięcie sprzed ≤ momentum_max sesji, kurs nad SMA średnią",
    "3 Trend dojrzały": "SMA krótka > średnia > długa, SMA średnia rośnie, kurs nad SMA średnią",
    "4 Przegrzanie": "kurs > SMA średnia o > overheat_dist lub RSI14 > rsi_overheat",
    "5 Osłabienie": "SMA krótka > średnia, ale kurs zszedł pod SMA średnią",
}
GOOD_PHASES = ("1 Zapłon", "2 Rozpęd", "3 Trend dojrzały")
