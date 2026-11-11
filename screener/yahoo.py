# -*- coding: utf-8 -*-
"""Warstwa danych Yahoo: lista spółek z wyszukiwarki, flagi fundamentów, kursy walut, notowania, info."""
from __future__ import annotations

import datetime as dt
import os
import random
import time

import numpy as np
import pandas as pd

from .config import CFG, MINOR_CURRENCIES

INFO_KEYS = [
    "shortName", "sector", "industry", "marketCap", "priceToSalesTrailing12Months", "trailingPE",
    "forwardPE", "profitMargins", "operatingMargins", "returnOnEquity", "revenueGrowth",
    "earningsGrowth", "debtToEquity",
]


def _retry(fn, label: str, tries: int = 5, base: float = 3.0):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            wait = base * 2 ** i + random.random() * 2
            print(f"   ! {label}: {str(e)[:140]} – ponowienie {i + 1}/{tries} za {wait:.0f}s")
            time.sleep(wait)
    return None


# ───────────────────────── wyszukiwarka (lista spółek + flagi) ─────────────────────────
def _base_query(country: str, exchanges: list[str]):
    from yfinance import EquityQuery as Q

    exq = Q("eq", ["exchange", exchanges[0]]) if len(exchanges) == 1 else Q("is-in", ["exchange", *exchanges])
    return [Q("eq", ["region", country]), exq]


def _screen_all(operands: list, limit: int, label: str) -> list[dict] | None:
    import yfinance as yf
    from yfinance import EquityQuery as Q

    query = Q("and", operands)
    out, offset = [], 0
    while offset < limit:
        size = min(250, limit - offset)
        r = _retry(lambda: yf.screen(query, offset=offset, size=size,
                                     sortField="intradaymarketcap", sortAsc=False), label)
        if r is None:
            return None if not out else out
        quotes = r.get("quotes", []) or []
        out.extend(quotes)
        offset += size
        if len(quotes) < size or offset >= int(r.get("total") or 0):
            break
        time.sleep(1.0)
    return out


def build_universe(region: str, rcfg: dict, cache_dir: str, force: bool = False) -> pd.DataFrame:
    """Lista spółek regionu + flagi fundamentów. Cache odświeżany co universe_max_age_days."""
    from yfinance import EquityQuery as Q

    path = os.path.join(cache_dir, f"{region}.csv")
    if os.path.exists(path) and not force:
        old = pd.read_csv(path)
        age = (dt.date.today() - pd.to_datetime(old["Odświeżono"].iloc[0]).date()).days
        if age < CFG["universe_max_age_days"]:
            print(f"▶ lista spółek z cache ({len(old)} szt., {age} dni)")
            return old

    rows = []
    for country, cc in rcfg["countries"].items():
        base = _base_query(country, cc["exchanges"])
        quotes = _screen_all(base, cc["top"], f"lista {country}")
        if not quotes:
            print(f"  ! {country}: wyszukiwarka nie zwróciła danych")
            continue
        uni = pd.DataFrame([{
            "Ticker": q.get("symbol"),
            "Nazwa": q.get("longName") or q.get("shortName"),
            "Kraj": country.upper(),
            "Giełda": q.get("exchange"),
            "Waluta": q.get("currency"),
            "Kapitalizacja (lok.)": q.get("marketCap"),
            "Typ": q.get("quoteType"),
        } for q in quotes])
        uni = uni[uni["Typ"].fillna("EQUITY") == "EQUITY"].drop(columns="Typ")
        floor = float(uni["Kapitalizacja (lok.)"].dropna().min() or 0) * 0.9
        cap = [Q("gte", ["intradaymarketcap", floor])] if floor > 0 else []
        flag_defs = {
            "F: marża netto>0": Q("gt", ["netincomemargin.lasttwelvemonths", 0]),
            "F: wzrost przych.>0": Q("gt", ["totalrevenues1yrgrowth.lasttwelvemonths", 0]),
            "F: ROE≥próg": Q("gte", ["returnonequity.lasttwelvemonths", CFG["roe_min_pct"]]),
            "F: 0<P/S≤próg": Q("btwn", ["lastclosemarketcaptotalrevenue.lasttwelvemonths", 0, CFG["ps_max"]]),
        }
        for col, cond in flag_defs.items():
            res = _screen_all(base + cap + [cond], cc["top"] + 500, f"{col} {country}")
            if res is None:
                uni[col] = np.nan
            else:
                hit = {q.get("symbol") for q in res}
                uni[col] = uni["Ticker"].isin(hit).astype(int)
                share = uni[col].mean()
                print(f"   {country} {col}: {share:.0%} spółek spełnia")
                if col == "F: ROE≥próg" and len(uni) > 50 and (share > 0.9 or share < 0.02):
                    print("   ! podejrzany udział ROE – sprawdź, czy Yahoo podaje ROE w % (roe_min_pct w config.py)")
        rows.append(uni)
        print(f"  ✔ {country}: {len(uni)} spółek")

    if not rows:
        if os.path.exists(path):
            print("  ! wyszukiwarka niedostępna – używam starej listy z cache")
            return pd.read_csv(path)
        raise SystemExit(f"Brak listy spółek dla regionu {region} i brak cache.")
    df = pd.concat(rows, ignore_index=True).drop_duplicates("Ticker")
    df["Odświeżono"] = dt.date.today().isoformat()
    os.makedirs(cache_dir, exist_ok=True)
    df.to_csv(path, index=False)
    return df


# ───────────────────────── waluty ─────────────────────────
def normalize_currency(cur: str | None) -> tuple[str, float]:
    """Zwraca (waluta główna, dzielnik ceny). GBp → (GBP, 100)."""
    if not isinstance(cur, str) or not cur:
        return "USD", 1.0
    return MINOR_CURRENCIES.get(cur, (cur.upper(), 1.0))


def fx_to_usd(currencies: set[str]) -> dict[str, float]:
    import yfinance as yf

    rates = {"USD": 1.0}
    need = sorted(c for c in currencies if c != "USD")
    if not need:
        return rates
    pairs = [f"{c}USD=X" for c in need]
    raw = _retry(lambda: yf.download(pairs, period="10d", auto_adjust=False, progress=False,
                                     group_by="ticker", threads=True), "kursy walut")
    for c, p in zip(need, pairs):
        try:
            s = (raw[p] if isinstance(raw.columns, pd.MultiIndex) else raw)["Close"].dropna()
            rates[c] = float(s.iloc[-1])
        except Exception:  # noqa: BLE001
            print(f"  ! brak kursu {c}/USD – płynność tej waluty liczona bez przeliczenia")
            rates[c] = np.nan
    return rates


# ───────────────────────── notowania ─────────────────────────
def download_prices(tickers: list[str], years: int) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    out, n = {}, CFG["chunk"]
    min_len = CFG["sma_long"] + CFG["window"]
    for i in range(0, len(tickers), n):
        chunk = tickers[i:i + n]

        def get():
            raw = yf.download(chunk, period=f"{years}y", interval="1d", auto_adjust=True,
                              group_by="ticker", threads=True, progress=False)
            if raw is None or raw.empty:
                raise RuntimeError("pusta odpowiedź (limit Yahoo?)")
            return raw

        raw = _retry(get, f"notowania {i}-{i + len(chunk)}", tries=4, base=10)
        if raw is not None:
            for t in chunk:
                try:
                    df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
                    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
                    if len(df) >= min_len:
                        out[t] = df
                except Exception:  # noqa: BLE001
                    pass
        print(f"   notowania: {min(i + n, len(tickers))}/{len(tickers)} (ok: {len(out)})")
        time.sleep(CFG["chunk_pause_s"])
    return out


def fetch_info(tickers: list[str]) -> dict[str, dict]:
    import yfinance as yf

    out = {}
    for t in tickers:
        info = _retry(lambda: yf.Ticker(t).info or {}, f"info {t}", tries=3, base=5) or {}
        out[t] = {k: info.get(k) for k in INFO_KEYS}
        time.sleep(CFG["info_pause_s"])
    return out
