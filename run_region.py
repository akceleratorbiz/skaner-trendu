#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skan jednego regionu:  python run_region.py --region eu  [--demo] [--force-universe]

Wynik (folder output/):
  <region>.csv               ranking wszystkich spółek regionu
  <region>.xlsx              arkusz regionu: Kandydaci, Ranking, Klimat rynku, Backtest
  <region>_backtest.csv      sumy backtestu (do łączenia globalnie)
  <region>_klimat.csv        szerokość rynku (do arkusza zbiorczego)
Lista spółek i flagi fundamentów: data/universe/<region>.csv (cache tygodniowy)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import numpy as np
import pandas as pd

from screener.config import CFG, GOOD_PHASES, REGIONS
from screener.core import backtest_sums, backtest_table, features, snapshot
from screener.excel import write_df

FLAG_COLS = ["F: marża netto>0", "F: wzrost przych.>0", "F: ROE≥próg", "F: 0<P/S≤próg"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True, choices=sorted(REGIONS))
    ap.add_argument("--demo", action="store_true", help="dane syntetyczne, bez internetu")
    ap.add_argument("--force-universe", action="store_true", help="odśwież listę spółek mimo cache")
    ap.add_argument("--limit", type=int, default=0, help="test: weź tylko N pierwszych spółek")
    ap.add_argument("--out-dir", default="output")
    ap.add_argument("--cache-dir", default="data/universe")
    a = ap.parse_args()

    t0 = time.time()
    region, rcfg = a.region, REGIONS[a.region]
    print(f"══ REGION {region.upper()} – {rcfg['name']} ══")

    if a.demo:
        from screener import demo as src
        uni = src.demo_universe(region, rcfg)
    else:
        from screener import yahoo as src
        uni = src.build_universe(region, rcfg, a.cache_dir, force=a.force_universe)
    if a.limit:
        uni = uni.head(a.limit)

    # waluty: GBp → GBP/100 itd.
    from screener.yahoo import normalize_currency
    norm = uni["Waluta"].map(normalize_currency)
    uni["Waluta gł."] = norm.map(lambda x: x[0])
    uni["_div"] = norm.map(lambda x: x[1])
    fx = src.demo_fx(set(uni["Waluta gł."])) if a.demo else src.fx_to_usd(set(uni["Waluta gł."]))
    print(f"▶ kursy walut: { {k: round(v, 5) for k, v in fx.items()} }")

    tickers = uni["Ticker"].dropna().tolist()
    print(f"▶ notowania dla {len(tickers)} spółek…")
    prices = src.demo_prices(tickers, CFG["price_years"]) if a.demo else src.download_prices(tickers, CFG["price_years"])
    if not prices:
        sys.exit("Brak notowań – Yahoo zablokowało zapytania albo lista jest pusta.")

    meta = uni.set_index("Ticker")
    rows, sums = [], []
    for t, df in prices.items():
        m = meta.loc[t]
        div = float(m["_div"])
        if div != 1:
            df = df.copy()
            df[["Open", "High", "Low", "Close"]] = df[["Open", "High", "Low", "Close"]] / div
        f = features(df)
        rate = fx.get(m["Waluta gł."], np.nan)
        rows.append(snapshot(t, df, f, rate if pd.notna(rate) else 1.0))
        sums.append(backtest_sums({t: f[["close", "phase", "wst21", "sma_l"]]}))

    rk = pd.DataFrame(rows).merge(
        uni.drop(columns=["_div"]).rename(columns={"Waluta gł.": "Waluta (gł.)"}), on="Ticker", how="left")
    rk["Region"] = region
    min_turn = rcfg.get("min_turnover_usd", CFG["min_turnover_usd"])
    rk["Płynna"] = np.where((rk["Kurs (USD)"] >= CFG["min_price_usd"]) & (rk["Obrót 50s (USD)"] >= min_turn), "tak", "nie")

    flags = rk[[c for c in FLAG_COLS if c in rk]]
    rk["Fundamenty (0–100)"] = (flags.fillna(0).sum(axis=1) * 25).astype(int)
    rk["Kompletność fund."] = flags.notna().sum(axis=1).astype(str) + "/4"
    rk["Ocena"] = (CFG["w_wst"] * rk["WST"] + CFG["w_fund"] * rk["Fundamenty (0–100)"]).round(1)
    rk["Kapitalizacja (mld lok.)"] = rk.pop("Kapitalizacja (lok.)") / 1e9

    # pełne liczby fundamentów dla najlepszych kandydatów regionu
    cand = rk[(rk["Płynna"] == "tak") & rk["Faza"].isin(GOOD_PHASES)].sort_values("Ocena", ascending=False)
    top = cand["Ticker"].head(CFG["info_top_n"]).tolist()
    print(f"▶ szczegóły fundamentów dla {len(top)} kandydatów…")
    info = src.demo_info(top) if a.demo else src.fetch_info(top)
    imap = {"priceToSalesTrailing12Months": "P/S", "trailingPE": "P/E", "forwardPE": "Fwd P/E",
            "profitMargins": "Marża netto", "operatingMargins": "Marża operacyjna", "returnOnEquity": "ROE",
            "revenueGrowth": "Wzrost przychodów r/r", "earningsGrowth": "Wzrost zysku r/r",
            "debtToEquity": "Dług/Kapitał (%)", "sector": "Sektor"}
    idf = pd.DataFrame.from_dict(info, orient="index").rename(columns=imap)
    idf = idf[[c for c in imap.values() if c in idf]]
    rk = rk.merge(idf, left_on="Ticker", right_index=True, how="left")

    first = ["Ticker", "Nazwa", "Kraj", "Faza", "Ocena", "WST", "WST 21s (start)", "Fundamenty (0–100)",
             "Wiek trendu (sesje)", "Trend od", "Płynna", "Sektor"]
    rk = rk[[c for c in first if c in rk] + [c for c in rk.columns if c not in first]]
    rk = rk.sort_values(["Ocena", "WST"], ascending=False)

    # klimat rynku (tylko płynne)
    liq = rk[rk["Płynna"] == "tak"]
    base = liq if len(liq) else rk
    ph = base["Faza"].value_counts(normalize=True)
    klimat = pd.DataFrame([{
        "Region": region, "Nazwa regionu": rcfg["name"], "Spółek w skanie": len(rk), "Płynnych": len(liq),
        "% spółek SMA20>SMA50": (base["Faza"] != "0 Brak trendu").mean(),
        "% spółek nad SMA200": (base["Odl. od SMA200"] > 0).mean(),
        "% w fazie Zapłon": ph.get("1 Zapłon", 0.0), "% w fazie Rozpęd": ph.get("2 Rozpęd", 0.0),
        "% w trendzie dojrzałym": ph.get("3 Trend dojrzały", 0.0), "% przegrzanych": ph.get("4 Przegrzanie", 0.0),
        "Mediana WST": base["WST"].median(), "Śr. Ocena TOP20": cand["Ocena"].head(20).mean(),
        "Data notowań": str(rk["Data notowania"].max()), "Wygenerowano": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }])

    bts = pd.concat(sums, ignore_index=True).groupby(["Faza", "Podgrupa", "Horyzont"], as_index=False)[["n", "suma", "trafienia"]].sum()
    bt = backtest_table(bts)

    os.makedirs(a.out_dir, exist_ok=True)
    rk.to_csv(f"{a.out_dir}/{region}.csv", index=False)
    bts.to_csv(f"{a.out_dir}/{region}_backtest.csv", index=False)
    klimat.to_csv(f"{a.out_dir}/{region}_klimat.csv", index=False)

    stamp = f"{rcfg['name']} | notowania do {klimat['Data notowań'].iloc[0]}" + (" | DEMO: DANE SYNTETYCZNE" if a.demo else "")
    with pd.ExcelWriter(f"{a.out_dir}/{region}.xlsx", engine="openpyxl") as xw:
        write_df(xw, rk[(rk["Płynna"] == "tak") & rk["Faza"].isin(GOOD_PHASES)].head(200), "Kandydaci", f"Kandydaci – {stamp}", "Płynne spółki w fazach Zapłon / Rozpęd / Trend dojrzały, wg Oceny.")
        write_df(xw, rk, "Ranking", f"Ranking całego regionu – {stamp}")
        write_df(xw, klimat.T.reset_index().rename(columns={"index": "Miara", 0: "Wartość"}),
                 "Klimat rynku", f"Klimat rynku – {stamp}", freeze_col="A")
        write_df(xw, bt, "Backtest", f"Backtest faz – {stamp}",
                 "Zdarzenie = pierwszy dzień wejścia w fazę. Porównuj z wierszem BAZA.", freeze_col="C")

    print(f"✔ {region}: {len(rk)} spółek, {len(liq)} płynnych, kandydatów {len(cand)} – {time.time() - t0:.0f}s")
    print(rk[["Ticker", "Faza", "Ocena", "WST", "Płynna"]].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
