# -*- coding: utf-8 -*-
"""Formatowanie arkuszy Excel (wspólne dla arkuszy regionów i arkusza zbiorczego)."""
from __future__ import annotations

import pandas as pd

PCT_COLS = {
    "Zwrot kwartał", "% dni wzrostowych (kw.)", "% dni nad SMA50 (kw.)", "Tempo roczne (regresja)",
    "Momentum Clenow", "Max obsunięcie (kw.)", "Odl. od SMA50", "Odl. od SMA200", "Marża netto",
    "Marża operacyjna", "ROE", "Wzrost przychodów r/r", "Wzrost zysku r/r",
    "% spółek SMA20>SMA50", "% spółek nad SMA200", "% w fazie Zapłon", "% w fazie Rozpęd",
    "% w trendzie dojrzałym", "% przegrzanych",
}
NUM2 = {"R² log-ceny (kw.)", "Efficiency Ratio (kw.)"}
NUM1 = {"P/S", "P/E", "Fwd P/E", "Dług/Kapitał (%)", "Kapitalizacja (mld lok.)", "Mediana WST", "Śr. Ocena TOP20"}
INT_SEP = {"Obrót 50s (USD)"}
PHASE_FILL = {
    "1 Zapłon": "C6EFCE", "2 Rozpęd": "A9D08E", "3 Trend dojrzały": "DDEBF7",
    "4 Przegrzanie": "FCE4D6", "5 Osłabienie": "FFF2CC", "0 Brak trendu": "EDEDED",
}
SCORE_COLS = ("Ocena", "WST", "WST 21s (start)", "Fundamenty (0–100)")


def write_df(xw, df: pd.DataFrame, sheet: str, title: str, note: str = "", freeze_col: str = "C"):
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    df.to_excel(xw, sheet_name=sheet, index=False, startrow=3)
    ws = xw.book[sheet]
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=13, color="1F3864")
    if note:
        ws["A2"] = note
        ws["A2"].font = Font(italic=True, size=9, color="595959")
    head = PatternFill("solid", fgColor="1F3864")
    for cell in ws[4]:
        cell.fill, cell.font = head, Font(bold=True, color="FFFFFF")
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[4].height = 34
    ws.freeze_panes = f"{freeze_col}5"
    hdr = [c.value for c in ws[4]]
    last = ws.max_row
    for j, h in enumerate(hdr, 1):
        col = get_column_letter(j)
        ws.column_dimensions[col].width = max(9, min(28, len(str(h)) + 2))
        h = str(h)
        fmt = None
        if h in PCT_COLS or h.startswith(("Śr. zwrot", "Trafność")):
            fmt = "0.0%"
        elif h in NUM2:
            fmt = "0.00"
        elif h in NUM1:
            fmt = "0.0"
        elif h in INT_SEP:
            fmt = "#,##0"
        elif h in ("Trend od", "Data notowania"):
            fmt = "yyyy-mm-dd"
        if fmt:
            for r in range(5, last + 1):
                ws[f"{col}{r}"].number_format = fmt
        if h in SCORE_COLS and last >= 5:
            ws.conditional_formatting.add(
                f"{col}5:{col}{last}",
                ColorScaleRule(start_type="num", start_value=0, start_color="F8696B",
                               mid_type="num", mid_value=50, mid_color="FFEB84",
                               end_type="num", end_value=100, end_color="63BE7B"))
        if h == "Faza":
            ws.column_dimensions[col].width = 18
            for r in range(5, last + 1):
                v = ws[f"{col}{r}"].value
                if v in PHASE_FILL:
                    ws[f"{col}{r}"].fill = PatternFill("solid", fgColor=PHASE_FILL[v])
        if h in ("Nazwa", "Wniosek", "Definicja"):
            ws.column_dimensions[col].width = 30 if h == "Nazwa" else 90
    if hdr and last >= 5:
        ws.auto_filter.ref = f"A4:{get_column_letter(len(hdr))}{last}"
    return ws
