# -*- coding: utf-8 -*-
"""Dane syntetyczne do testu całego potoku bez internetu (--demo)."""
from __future__ import annotations

import datetime as dt
import zlib

import numpy as np
import pandas as pd

from .config import CFG

CUR = {"us": "USD", "ca": "CAD", "gb": "GBp", "de": "EUR", "fr": "EUR", "it": "EUR", "ch": "CHF",
       "nl": "EUR", "es": "EUR", "be": "EUR", "at": "EUR", "pt": "EUR", "ie": "EUR", "se": "SEK",
       "no": "NOK", "dk": "DKK", "fi": "EUR", "jp": "JPY", "au": "AUD", "hk": "HKD", "kr": "KRW",
       "sg": "SGD", "il": "ILA", "nz": "NZD", "pl": "PLN"}
FX = {"USD": 1, "CAD": 0.72, "GBP": 1.27, "EUR": 1.08, "CHF": 1.12, "SEK": 0.095, "NOK": 0.093,
      "DKK": 0.145, "JPY": 0.0066, "AUD": 0.65, "HKD": 0.128, "KRW": 0.00072, "SGD": 0.74,
      "ILS": 0.27, "NZD": 0.6, "PLN": 0.25}


def demo_universe(region: str, rcfg: dict, per_country: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(zlib.crc32(region.encode()))
    rows = []
    for country, cc in rcfg["countries"].items():
        n = min(per_country, cc["top"])
        for i in range(n):
            rows.append({
                "Ticker": f"{country.upper()}{i:03d}.DEMO", "Nazwa": f"Demo {country.upper()} {i}",
                "Kraj": country.upper(), "Giełda": cc["exchanges"][0], "Waluta": CUR[country],
                "Kapitalizacja (lok.)": float(rng.uniform(3e8, 5e11)),
                "F: marża netto>0": int(rng.random() < 0.7), "F: wzrost przych.>0": int(rng.random() < 0.6),
                "F: ROE≥próg": int(rng.random() < 0.35), "F: 0<P/S≤próg": int(rng.random() < 0.75),
            })
    df = pd.DataFrame(rows)
    df["Odświeżono"] = dt.date.today().isoformat()
    return df


def demo_prices(tickers: list[str], years: int) -> dict[str, pd.DataFrame]:
    n = 252 * years
    idx = pd.bdate_range(end=dt.date.today(), periods=n)
    out = {}
    for t in tickers:
        rng = np.random.default_rng(zlib.crc32(t.encode()))
        drift, pos = np.zeros(n), 0
        while pos < n:
            ln = int(rng.integers(40, 160))
            drift[pos:pos + ln] = rng.choice([0.0015, 0.0, -0.001], p=[0.45, 0.35, 0.2])
            pos += ln
        close = 50 * np.exp(np.cumsum(drift + rng.normal(0, rng.uniform(0.012, 0.03), n)))
        out[t] = pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                               "Volume": rng.integers(50_000, 3_000_000, n)}, index=idx)
    return out


def demo_info(tickers: list[str]) -> dict[str, dict]:
    out = {}
    for t in tickers:
        rng = np.random.default_rng(zlib.crc32(t.encode()) + 1)
        out[t] = {
            "shortName": f"Demo {t}", "sector": rng.choice(["Technology", "Industrials", "Healthcare", "Financials"]),
            "industry": "Demo", "marketCap": float(rng.uniform(3e8, 5e11)),
            "priceToSalesTrailing12Months": float(rng.uniform(0.5, 15)), "trailingPE": float(rng.uniform(8, 60)),
            "forwardPE": float(rng.uniform(8, 45)), "profitMargins": float(rng.uniform(-0.1, 0.35)),
            "operatingMargins": float(rng.uniform(-0.05, 0.4)), "returnOnEquity": float(rng.uniform(-0.1, 0.45)),
            "revenueGrowth": float(rng.uniform(-0.15, 0.5)), "earningsGrowth": float(rng.uniform(-0.3, 0.8)),
            "debtToEquity": float(rng.uniform(0, 200)),
        }
    return out


def demo_fx(currencies) -> dict[str, float]:
    return {c: FX.get(c, 1.0) for c in currencies} | {"USD": 1.0}


_ = CFG  # (parametry wspólne)
