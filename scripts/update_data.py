from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = "2020-01-01"
TZ = ZoneInfo("Asia/Seoul")
TODAY_KST = datetime.now(TZ).date()
# yfinance end is exclusive, so add a small buffer.
END_DATE = (TODAY_KST + timedelta(days=2)).isoformat()

@dataclass(frozen=True)
class Security:
    id: str
    ticker: str
    name: str
    kind: str  # stock, benchmark, portfolio
    market: str

STOCKS: List[Security] = [
    Security("SAMSUNG_ELEC", "005930.KS", "삼성전자", "stock", "KRX"),
    Security("SKHYNIX", "000660.KS", "SK하이닉스", "stock", "KRX"),
    Security("KIA", "000270.KS", "기아", "stock", "KRX"),
    Security("SHINHAN", "055550.KS", "신한지주", "stock", "KRX"),
    Security("AMOREPACIFIC", "090430.KS", "아모레퍼시픽", "stock", "KRX"),
    Security("SKYLIFE", "053210.KS", "스카이라이프", "stock", "KRX"),
    Security("CJENM", "035760.KQ", "CJ ENM", "stock", "KOSDAQ"),
    Security("SHINWON", "009270.KS", "신원", "stock", "KRX"),
    Security("DONGYANG_EXP", "084670.KS", "동양고속", "stock", "KRX"),
    Security("UNID", "014830.KS", "유니드", "stock", "KRX"),
    Security("HANSSEM", "009240.KS", "한샘", "stock", "KRX"),
    Security("SEOYONEHWA", "200880.KS", "서연이화", "stock", "KRX"),
    Security("SAMYANGFOODS", "003230.KS", "삼양식품", "stock", "KRX"),
]

BENCHMARKS: List[Security] = [
    Security("KOSPI", "^KS11", "코스피", "benchmark", "INDEX"),
    Security("SP500", "^GSPC", "S&P 500", "benchmark", "INDEX"),
    Security("NASDAQ", "^IXIC", "나스닥", "benchmark", "INDEX"),
]

PORTFOLIO = Security("DGU_PORTFOLIO", "DGU", "DGU 포트폴리오", "portfolio", "CUSTOM")


def clean_number(x):
    if x is None:
        return None
    try:
        if pd.isna(x) or not math.isfinite(float(x)):
            return None
        return round(float(x), 4)
    except Exception:
        return None


def download_close_series(sec: Security) -> pd.Series:
    print(f"Downloading {sec.name} ({sec.ticker})...")
    df = yf.download(
        sec.ticker,
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df.empty:
        raise RuntimeError(f"No data returned for {sec.name} ({sec.ticker})")

    # yfinance may return MultiIndex columns depending on version/settings.
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
        elif "Close" in df.columns.get_level_values(-1):
            close = df.xs("Close", level=-1, axis=1).iloc[:, 0]
        else:
            raise RuntimeError(f"Close column not found for {sec.ticker}")
    else:
        close = df["Close"]

    close = close.dropna().astype(float)
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close[close.index >= pd.Timestamp(START_DATE)]
    if close.empty:
        raise RuntimeError(f"No close data after {START_DATE} for {sec.ticker}")
    return close


def build_series_payload(series: pd.Series, start_price: float) -> list:
    normalized = series / start_price * 100
    payload = []
    for dt, close in series.items():
        payload.append([
            dt.strftime("%Y-%m-%d"),
            clean_number(normalized.loc[dt]),
            clean_number(close),
        ])
    return payload


def build_metric(sec: Security, series: pd.Series, start_price: float) -> dict:
    latest_date = series.index[-1]
    latest_price = float(series.iloc[-1])
    initial_invested = float(start_price)
    profit = latest_price - initial_invested
    return {
        "id": sec.id,
        "ticker": sec.ticker,
        "name": sec.name,
        "kind": sec.kind,
        "market": sec.market,
        "startDate": series.index[0].strftime("%Y-%m-%d"),
        "startPrice": clean_number(start_price),
        "latestDate": latest_date.strftime("%Y-%m-%d"),
        "latestPrice": clean_number(latest_price),
        "initialShares": 1 if sec.kind == "stock" else None,
        "initialInvested": clean_number(initial_invested),
        "currentValue": clean_number(latest_price),
        "profit": clean_number(profit),
        "returnPct": clean_number((latest_price / start_price - 1) * 100),
    }


def main() -> None:
    raw_series: Dict[str, pd.Series] = {}
    errors: List[str] = []

    for sec in STOCKS + BENCHMARKS:
        try:
            raw_series[sec.id] = download_close_series(sec)
        except Exception as exc:
            msg = f"{sec.name} ({sec.ticker}): {exc}"
            print("ERROR:", msg, file=sys.stderr)
            errors.append(msg)

    if errors:
        # Fail the workflow rather than silently publishing partial data.
        raise RuntimeError("Data download failed: " + "; ".join(errors))

    assets = []
    series_payload = {}
    metrics = []

    for sec in STOCKS + BENCHMARKS:
        s = raw_series[sec.id]
        start_price = float(s.iloc[0])
        assets.append(asdict(sec))
        series_payload[sec.id] = build_series_payload(s, start_price)
        metrics.append(build_metric(sec, s, start_price))

    # Equal-share DGU portfolio: buy one share of each listed DGU stock at its first trading-day close.
    stock_df = pd.concat({sec.id: raw_series[sec.id] for sec in STOCKS}, axis=1).sort_index().ffill()
    stock_df = stock_df.dropna(how="any")
    portfolio_value = stock_df.sum(axis=1)
    portfolio_start = float(sum(raw_series[sec.id].iloc[0] for sec in STOCKS))

    assets.insert(0, asdict(PORTFOLIO))
    series_payload[PORTFOLIO.id] = build_series_payload(portfolio_value, portfolio_start)
    metrics.insert(0, {
        "id": PORTFOLIO.id,
        "ticker": PORTFOLIO.ticker,
        "name": PORTFOLIO.name,
        "kind": PORTFOLIO.kind,
        "market": PORTFOLIO.market,
        "startDate": portfolio_value.index[0].strftime("%Y-%m-%d"),
        "startPrice": clean_number(portfolio_start),
        "latestDate": portfolio_value.index[-1].strftime("%Y-%m-%d"),
        "latestPrice": clean_number(float(portfolio_value.iloc[-1])),
        "initialShares": "각 종목 1주",
        "initialInvested": clean_number(portfolio_start),
        "currentValue": clean_number(float(portfolio_value.iloc[-1])),
        "profit": clean_number(float(portfolio_value.iloc[-1] - portfolio_start)),
        "returnPct": clean_number((float(portfolio_value.iloc[-1]) / portfolio_start - 1) * 100),
    })

    payload = {
        "meta": {
            "title": "DGU Portfolio",
            "startRule": "2020-01-01 이후 첫 거래일 종가를 시작가로 사용",
            "baseValue": 100,
            "priceField": "Close",
            "currencyNote": "국내 종목은 KRW, 미국 지수는 index level. 차트는 모두 시작점 100으로 정규화.",
            "generatedAt": datetime.now(TZ).isoformat(timespec="seconds"),
            "timezone": "Asia/Seoul",
            "source": "Yahoo Finance via yfinance",
        },
        "assets": assets,
        "metrics": metrics,
        "series": series_payload,
    }

    json_path = DATA_DIR / "portfolio.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = DATA_DIR / "price-table.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metrics[0].keys()))
        writer.writeheader()
        writer.writerows(metrics)

    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
