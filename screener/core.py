# -*- coding: utf-8 -*-
"""Wskaźniki, fazy, WST, migawka bieżąca i backtest. Ta sama logika dla rankingu i weryfikacji."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CFG


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def run_length(mask: pd.Series) -> pd.Series:
    """Ile kolejnych sesji (łącznie z bieżącą) warunek jest spełniony."""
    m = mask.astype(int)
    return m.groupby((m != m.shift()).cumsum()).cumsum()


def features(df: pd.DataFrame) -> pd.DataFrame:
    c, w = df["Close"], CFG["window"]
    f = pd.DataFrame(index=df.index)
    f["close"] = c
    f["sma_s"] = c.rolling(CFG["sma_short"]).mean()
    f["sma_m"] = c.rolling(CFG["sma_mid"]).mean()
    f["sma_l"] = c.rolling(CFG["sma_long"]).mean()
    f["rsi"] = rsi(c)
    above = f["sma_s"] > f["sma_m"]
    f["age"] = run_length(above)
    f["age_golden"] = run_length(f["sma_m"] > f["sma_l"])
    f["sma_m_slope"] = f["sma_m"].pct_change(10)

    logc = np.log(c)
    t = pd.Series(np.arange(len(c)), index=c.index, dtype=float)

    def wst_parts(win, ref_ma):
        r2 = t.rolling(win).corr(logc) ** 2
        slope = t.rolling(win).cov(logc) / t.rolling(win).var()
        er = (c - c.shift(win)).abs() / c.diff().abs().rolling(win).sum()
        pct_above = (c > ref_ma).astype(float).rolling(win).mean()
        er_n = (er / CFG["er_full"]).clip(upper=1)
        wst = (100 * (0.4 * r2 + 0.3 * er_n + 0.3 * pct_above)).where(slope > 0, 0.0)
        return r2, slope, er, pct_above, wst

    f["r2"], slope, f["er"], f["pct_above_m"], f["wst"] = wst_parts(w, f["sma_m"])
    *_, f["wst21"] = wst_parts(CFG["window_short"], f["sma_s"])
    f["slope_ann"] = np.exp(slope * 252) - 1
    f["pct_up_days"] = (c.diff() > 0).astype(float).rolling(w).mean()
    f["ret_q"] = c / c.shift(w) - 1
    f["clenow"] = f["slope_ann"] * f["r2"]

    dist_m = c / f["sma_m"] - 1
    overheat = (dist_m > CFG["overheat_dist"]) | (f["rsi"] > CFG["rsi_overheat"])
    conds = [
        ~above,
        above & (f["age"] <= CFG["ignition_max"]) & (c > f["sma_s"]),
        above & overheat,
        above & (f["age"] <= CFG["momentum_max"]) & (c > f["sma_m"]),
        above & (f["sma_m"] > f["sma_l"]) & (c > f["sma_m"]) & (f["sma_m_slope"] > 0),
    ]
    names = ["0 Brak trendu", "1 Zapłon", "4 Przegrzanie", "2 Rozpęd", "3 Trend dojrzały"]
    f["phase"] = np.select(conds, names, default="5 Osłabienie")
    f["dist_m"] = dist_m
    f["dist_l"] = c / f["sma_l"] - 1
    f["turnover"] = (df["Close"] * df["Volume"]).rolling(50).mean()
    return f


def snapshot(t: str, df: pd.DataFrame, f: pd.DataFrame, fx_usd: float) -> dict:
    last = f.iloc[-1]
    c, w = df["Close"], CFG["window"]
    q = c.iloc[-w:]
    age = int(last["age"])
    return {
        "Ticker": t,
        "Faza": last["phase"],
        "WST": round(float(last["wst"]), 1),
        "WST 21s (start)": round(float(last["wst21"]), 1),
        "Wiek trendu (sesje)": age,
        "Trend od": f.index[-age].date() if age > 0 else None,
        "SMA50>SMA200 (sesje)": int(last["age_golden"]),
        "Kurs": round(float(last["close"]), 4),
        "Data notowania": f.index[-1].date(),
        "Zwrot kwartał": last["ret_q"],
        "% dni wzrostowych (kw.)": last["pct_up_days"],
        "Seria wzrostów (sesje)": int(run_length(c.diff() > 0).iloc[-1]),
        "Sesje nad SMA20": int(run_length(c > f["sma_s"]).iloc[-1]),
        "% dni nad SMA50 (kw.)": last["pct_above_m"],
        "R² log-ceny (kw.)": last["r2"],
        "Efficiency Ratio (kw.)": last["er"],
        "Tempo roczne (regresja)": last["slope_ann"],
        "Momentum Clenow": last["clenow"],
        "Max obsunięcie (kw.)": float((q / q.cummax() - 1).min()),
        "Odl. od SMA50": last["dist_m"],
        "Odl. od SMA200": last["dist_l"],
        "RSI14": round(float(last["rsi"]), 1),
        "Obrót 50s (USD)": float(last["turnover"]) * fx_usd if pd.notna(last["turnover"]) else np.nan,
        "Kurs (USD)": float(last["close"]) * fx_usd,
    }


def backtest_sums(feats: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Sumy (liczba, suma zwrotów, trafienia) per faza – dają się sumować między regionami."""
    warm = CFG["sma_long"] + CFG["window"]
    rows = []
    for _, f in feats.items():
        f = f.iloc[warm:]
        if f.empty:
            continue
        fwd = {h: f["close"].shift(-h) / f["close"] - 1 for h in CFG["fwd"]}
        entry = f["phase"] != f["phase"].shift()
        wst21_bucket = pd.cut(f["wst21"], [-0.1, 40, 60, 80, 100.1], labels=["<40", "40–60", "60–80", "≥80"])
        above200 = np.where(f["close"] > f["sma_l"], "kurs>SMA200", "kurs≤SMA200")
        for h, r in fwd.items():
            base = pd.DataFrame({"r": r}).dropna()
            rows.append(("BAZA: wszystkie dni", "", h, len(base), base["r"].sum(), (base["r"] > 0).sum()))
            ev = pd.DataFrame({"phase": f["phase"], "r": r, "b": wst21_bucket.astype(str),
                               "a": above200})[entry].dropna(subset=["r"])
            for ph, g in ev.groupby("phase"):
                rows.append((ph, "", h, len(g), g["r"].sum(), (g["r"] > 0).sum()))
            ign = ev[ev["phase"] == "1 Zapłon"]
            for (a, b), g in ign.groupby(["a", "b"]):
                rows.append(("1 Zapłon", f"{a} | WST21 {b}", h, len(g), g["r"].sum(), (g["r"] > 0).sum()))
    df = pd.DataFrame(rows, columns=["Faza", "Podgrupa", "Horyzont", "n", "suma", "trafienia"])
    return df.groupby(["Faza", "Podgrupa", "Horyzont"], as_index=False)[["n", "suma", "trafienia"]].sum()


def backtest_table(sums: pd.DataFrame) -> pd.DataFrame:
    """Z sum → tabela: liczba zdarzeń, średni zwrot i trafność per horyzont."""
    if sums.empty:
        return pd.DataFrame()
    s = sums.copy()
    s["Podgrupa"] = s["Podgrupa"].fillna("").astype(str)   # pusta podgrupa z CSV wraca jako NaN
    s = s.groupby(["Faza", "Podgrupa", "Horyzont"], as_index=False)[["n", "suma", "trafienia"]].sum()
    s["Śr. zwrot"] = s["suma"] / s["n"].where(s["n"] > 0)
    s["Trafność"] = s["trafienia"] / s["n"].where(s["n"] > 0)
    rows = []
    for (ph, sub), g in s.groupby(["Faza", "Podgrupa"], sort=False):
        g = g.set_index("Horyzont")
        r = {"Faza": ph, "Podgrupa": sub, "Zdarzenia": int(g["n"].max())}
        for h in CFG["fwd"]:
            r[f"Śr. zwrot {h}s"] = g["Śr. zwrot"].get(h, float("nan"))
            r[f"Trafność {h}s"] = g["Trafność"].get(h, float("nan"))
        rows.append(r)
    out = pd.DataFrame(rows)
    out["_o"] = out["Faza"].replace({"BAZA: wszystkie dni": "9"}) + out["Podgrupa"]
    return out.sort_values("_o").drop(columns="_o").reset_index(drop=True)
