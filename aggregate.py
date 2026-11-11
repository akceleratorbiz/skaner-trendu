#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arkusz zbiorczy ze wszystkich regionów:  python aggregate.py [--in-dir output] [--out-dir results]

Wynik (folder results/):
  SKANER_GLOBALNY.xlsx   TOP globalny, Zapłon, Rozpęd, TOP regionów, Klimat rynku, Backtest, Metodyka
  TOP.md                 podgląd na telefonie (GitHub renderuje tabelę)
  top.csv                TOP 100 globalnie
  regiony/<region>.xlsx  arkusze regionów
  historia/top_RRRR-MM-DD.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import shutil

import pandas as pd

from screener.config import CFG, GOOD_PHASES, PHASES, REGIONS
from screener.core import backtest_table
from screener.excel import write_df

VIEW = ["Region", "Kraj", "Ticker", "Nazwa", "Sektor", "Faza", "Ocena", "WST", "WST 21s (start)",
        "Fundamenty (0–100)", "Kompletność fund.", "Wiek trendu (sesje)", "Trend od", "Zwrot kwartał",
        "% dni wzrostowych (kw.)", "Odl. od SMA50", "Odl. od SMA200", "RSI14", "Max obsunięcie (kw.)",
        "P/S", "P/E", "ROE", "Marża netto", "Wzrost przychodów r/r", "Obrót 50s (USD)", "Waluta (gł.)",
        "Kurs", "Data notowania"]


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    def fmt(v, c):
        if pd.isna(v):
            return ""
        if c in ("Zwrot kwartał", "Odl. od SMA50", "ROE", "Marża netto", "% spółek SMA20>SMA50", "% spółek nad SMA200",
                 "% w fazie Zapłon", "% w fazie Rozpęd", "% spółek WST≥60"):
            return f"{v:.0%}"
        if isinstance(v, float):
            return f"{v:.1f}"
        return str(v).replace("|", "/")
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(r[c], c) for c in cols) + " |" for _, r in df.iterrows()]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default="output")
    ap.add_argument("--out-dir", default="results")
    a = ap.parse_args()

    files = sorted(f for f in glob.glob(f"{a.in_dir}/*.csv") if os.path.basename(f)[:-4] in REGIONS)
    if not files:
        raise SystemExit("Brak wyników regionów w " + a.in_dir)
    present = [os.path.basename(f)[:-4] for f in files]
    missing = [r for r in REGIONS if r not in present]
    g = pd.concat([pd.read_csv(f, parse_dates=["Trend od", "Data notowania"]) for f in files], ignore_index=True)
    klimat = pd.concat([pd.read_csv(f) for f in glob.glob(f"{a.in_dir}/*_klimat.csv")], ignore_index=True)
    bts = [pd.read_csv(f) for f in glob.glob(f"{a.in_dir}/*_backtest.csv")]
    bt = backtest_table(pd.concat(bts, ignore_index=True)) if bts else pd.DataFrame()

    liq = g[g["Płynna"] == "tak"]
    good = liq[liq["Faza"].isin(GOOD_PHASES)].sort_values(["Ocena", "WST"], ascending=False)
    view = [c for c in VIEW if c in g.columns]
    top = good[view].head(100)
    ign = liq[(liq["Faza"] == "1 Zapłon") & (liq["WST 21s (start)"] >= 60) & (liq["Fundamenty (0–100)"] >= 50)]
    ign = ign.sort_values(["Fundamenty (0–100)", "WST 21s (start)"], ascending=False)[view].head(100)
    mom = liq[liq["Faza"] == "2 Rozpęd"].sort_values("Ocena", ascending=False)[view].head(100)
    per_region = good.groupby("Region", group_keys=False).head(15)[view]
    klimat = klimat.sort_values("% spółek WST≥60", ascending=False)

    today = dt.date.today().isoformat()
    note = (f"Regiony: {', '.join(present)}" + (f" | BRAK DANYCH: {', '.join(missing)}" if missing else "")
            + f" | spółek w skanie: {len(g):,} | płynnych: {len(liq):,}".replace(",", " "))
    demo = g["Ticker"].astype(str).str.endswith(".DEMO").any()
    title_sfx = f" – {today}" + ("  |  DEMO: DANE SYNTETYCZNE" if demo else "")

    os.makedirs(f"{a.out_dir}/regiony", exist_ok=True)
    os.makedirs(f"{a.out_dir}/historia", exist_ok=True)
    meth = pd.DataFrame(
        list(PHASES.items()) + [
            ("Ocena", f"{CFG['w_wst']}·WST + {CFG['w_fund']}·Fundamenty."),
            ("WST (0–100)", "Kwartał (63 sesje): 40% R² regresji log-ceny + 30% Efficiency Ratio + 30% dni nad SMA50; 0 przy nachyleniu ≤ 0."),
            ("WST 21s (start)", "Ten sam wzór na 21 sesjach z SMA20 – ocena jakości świeżego startu."),
            ("Fundamenty (0–100)", f"Po 25 pkt: marża netto > 0, wzrost przychodów r/r > 0, ROE ≥ {CFG['roe_min_pct']}%, 0 < P/S ≤ {CFG['ps_max']}. Flagi z wyszukiwarki Yahoo dla całego regionu."),
            ("Płynna", f"Kurs ≥ {CFG['min_price_usd']} USD i średni obrót 50 sesji ≥ {CFG['min_turnover_usd']:,} USD (GPW: niższy próg).".replace(",", " ")),
            ("Zapłon – lista", "Faza 1 Zapłon, WST 21s ≥ 60, Fundamenty ≥ 50, tylko płynne."),
            ("Klimat rynku", "Szerokość rynku: jaki odsetek płynnych spółek regionu jest w trendzie. Niska = ostrożność z nowymi pozycjami."),
            ("Backtest", "Tylko spółki płynne. Zdarzenie = pierwszy dzień wejścia w fazę, zwroty po 5/20/63 sesjach przycięte do [-80%, +100%]. Sygnał ma wartość, gdy bije wiersz BAZA."),
            ("Ograniczenia", "Dane Yahoo (nieoficjalne), brak kosztów transakcyjnych, lista spółek z dziś (survivorship bias), fundamenty bieżące."),
        ], columns=["Pojęcie", "Definicja"])

    with pd.ExcelWriter(f"{a.out_dir}/SKANER_GLOBALNY.xlsx", engine="openpyxl") as xw:
        write_df(xw, top, "TOP globalny", "TOP 100 – rozwinięty świat" + title_sfx, note)
        write_df(xw, ign, "Zapłon", "Świeże starty z jakością (Zapłon)" + title_sfx, "Faza 1, WST 21s ≥ 60, Fundamenty ≥ 50.")
        write_df(xw, mom, "Rozpęd", "Rozpęd – TOP 100" + title_sfx)
        write_df(xw, per_region, "TOP regionów", "TOP 15 z każdego regionu" + title_sfx)
        write_df(xw, klimat, "Klimat rynku", "Klimat rynku – regiony" + title_sfx, freeze_col="B")
        if not bt.empty:
            write_df(xw, bt, "Backtest", "Backtest faz – wszystkie regiony razem" + title_sfx,
                     "Porównuj z wierszem BAZA: wszystkie dni.")
        write_df(xw, meth, "Metodyka", "Metodyka", freeze_col="A")

    top.to_csv(f"{a.out_dir}/top.csv", index=False)
    top.head(30).to_csv(f"{a.out_dir}/historia/top_{today}.csv", index=False)
    for r in present:
        src = f"{a.in_dir}/{r}.xlsx"
        if os.path.exists(src):
            shutil.copy(src, f"{a.out_dir}/regiony/{r}.xlsx")

    kcols = ["Nazwa regionu", "Płynnych", "% spółek SMA20>SMA50", "% spółek nad SMA200", "% spółek WST≥60", "% w fazie Zapłon"]
    tcols = ["Region", "Ticker", "Nazwa", "Faza", "Ocena", "WST", "Fundamenty (0–100)", "Wiek trendu (sesje)", "Zwrot kwartał"]
    icols = ["Region", "Ticker", "Nazwa", "WST 21s (start)", "Fundamenty (0–100)", "Wiek trendu (sesje)"]
    md = [f"# Skaner trendu – {today}" + (" (DEMO)" if demo else ""), "", note, "",
          "## Klimat rynku", md_table(klimat, [c for c in kcols if c in klimat]), "",
          "## TOP 30 globalnie", md_table(top.head(30), [c for c in tcols if c in top]), "",
          "## Zapłon – świeże starty z jakością", md_table(ign.head(20), [c for c in icols if c in ign]), "",
          "Pełne dane: `SKANER_GLOBALNY.xlsx` i `regiony/`. Materiał analityczny, nie rekomendacja."]
    with open(f"{a.out_dir}/TOP.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    print(f"✔ arkusz zbiorczy: {len(g)} spółek z {len(present)} regionów, TOP {len(top)}, Zapłon {len(ign)}")
    if missing:
        print("! brak regionów:", ", ".join(missing))


if __name__ == "__main__":
    main()
