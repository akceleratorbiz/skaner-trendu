#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
(Opcjonalnie) wysyłka wyników do Google Sheets.

Wymaga sekretów w GitHub (Settings → Secrets → Actions):
  GOOGLE_SA_JSON  – cała zawartość pliku JSON konta serwisowego Google
  SHEET_ID        – identyfikator arkusza (z adresu: /spreadsheets/d/<SHEET_ID>/edit)
Arkusz trzeba udostępnić (Edytor) adresowi e-mail konta serwisowego.
Bez sekretów skrypt kończy się bez błędu.
"""
from __future__ import annotations

import glob
import json
import os

import pandas as pd

from screener.config import REGIONS

MAX_ROWS = 300  # wierszy na zakładkę regionu


def to_values(df: pd.DataFrame) -> list[list]:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%d")
    df = df.astype(object).where(df.notna(), "")
    return [list(df.columns)] + df.values.tolist()


def put(sh, title: str, df: pd.DataFrame):
    import gspread

    try:
        ws = sh.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=max(100, len(df) + 10), cols=max(10, len(df.columns) + 2))
    vals = to_values(df)
    if ws.row_count < len(vals) or ws.col_count < len(vals[0]):
        ws.resize(rows=len(vals) + 10, cols=len(vals[0]) + 2)
    ws.update(values=vals, range_name="A1", value_input_option="USER_ENTERED")
    ws.freeze(rows=1)
    print(f"   ✔ {title}: {len(df)} wierszy")


def main():
    sa, sheet_id = os.environ.get("GOOGLE_SA_JSON"), os.environ.get("SHEET_ID")
    if not sa or not sheet_id:
        print("Brak GOOGLE_SA_JSON / SHEET_ID – pomijam wysyłkę do Google Sheets.")
        return
    import gspread

    gc = gspread.service_account_from_dict(json.loads(sa))
    sh = gc.open_by_key(sheet_id)
    xl = "results/SKANER_GLOBALNY.xlsx"
    for sheet, title in [("TOP globalny", "TOP"), ("Zapłon", "Zapłon"), ("Rozpęd", "Rozpęd"),
                         ("Klimat rynku", "Klimat rynku")]:
        try:
            put(sh, title, pd.read_excel(xl, sheet_name=sheet, header=3))
        except ValueError:
            pass
    for f in sorted(glob.glob("output/*.csv")):
        r = os.path.basename(f)[:-4]
        if r in REGIONS:
            df = pd.read_csv(f)
            put(sh, f"R: {REGIONS[r]['name']}", df[df["Płynna"] == "tak"].head(MAX_ROWS))


if __name__ == "__main__":
    main()
