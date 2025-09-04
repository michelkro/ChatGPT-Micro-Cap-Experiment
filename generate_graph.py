"""Utility functions to visualize portfolio performance against the S&P 500.

This module refactors and extends the original ``Generate_Graph.py`` script
from the ``Start Your Own`` folder.  The code is packaged so it can be used as a
stand‑alone CLI tool *and* imported by the Streamlit dashboard.  Key features
include:

* Normalising portfolio equity and S&P data to a common starting value.
* Automatic alignment and forward filling of S&P prices to portfolio dates.
* A small LRU cache to avoid redownloading the same S&P 500 date ranges.
* Helpers to produce a :class:`pandas.DataFrame` or an interactive Plotly
  figure for display inside the app.
"""

from __future__ import annotations

import argparse
from functools import lru_cache
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import yfinance as yf

DATA_DIR = Path(__file__).resolve().parent
PORTFOLIO_CSV = DATA_DIR / "Start Your Own" / "chatgpt_portfolio_update.csv"


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def parse_date(date_str: str, label: str) -> pd.Timestamp:
    """Parse a user supplied date string.

    Parameters
    ----------
    date_str:
        The text entered by the user.
    label:
        Name of the field for error messages.
    """
    try:
        return pd.to_datetime(date_str)
    except Exception as exc:  # pragma: no cover - argument errors
        raise SystemExit(f"Invalid {label} '{date_str}'. Use YYYY-MM-DD.") from exc


def _normalize_to_start(series: pd.Series, baseline: float) -> pd.Series:
    """Normalise values to ``baseline`` starting equity."""
    s = pd.to_numeric(series, errors="coerce")
    if s.empty:
        return pd.Series(dtype=float)
    start_value = s.iloc[0]
    if start_value == 0:
        return s * 0
    return (s / start_value) * baseline


def _align_to_dates(sp500: pd.DataFrame, dates: pd.Series) -> pd.Series:
    """Align S&P 500 close prices to ``dates`` with forward fill."""
    merged = pd.DataFrame({"Date": dates}).merge(sp500, on="Date", how="left")
    return merged["Value"].ffill()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_portfolio_details(
    start_date: Optional[pd.Timestamp],
    end_date: Optional[pd.Timestamp],
    portfolio_csv: Path = PORTFOLIO_CSV,
) -> pd.DataFrame:
    """Return TOTAL rows (Date, Total Equity) filtered to [start_date, end_date]."""

    if not portfolio_csv.exists():
        raise SystemExit(f"Portfolio file '{portfolio_csv}' not found.")

    df = pd.read_csv(portfolio_csv)
    totals = df[df["Ticker"] == "TOTAL"].copy()
    if totals.empty:
        raise SystemExit("Portfolio CSV contains no TOTAL rows.")

    totals["Date"] = pd.to_datetime(totals["Date"], errors="coerce")
    totals["Total Equity"] = pd.to_numeric(totals["Total Equity"], errors="coerce")
    totals = totals.dropna(subset=["Date", "Total Equity"]).sort_values("Date")

    min_date, max_date = totals["Date"].min(), totals["Date"].max()
    start_date = min_date if start_date is None or start_date < min_date else start_date
    end_date = max_date if end_date is None or end_date > max_date else end_date
    if start_date > end_date:
        raise SystemExit("Start date must be on or before end date.")

    mask = (totals["Date"] >= start_date) & (totals["Date"] <= end_date)
    return totals.loc[mask, ["Date", "Total Equity"]].reset_index(drop=True)


@lru_cache(maxsize=8)
def _download_sp500_series(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Download S&P 500 data between ``start`` and ``end`` (inclusive)."""
    try:  # pragma: no cover - network access
        df = yf.download("^GSPC", start=start, end=end + pd.Timedelta(days=1), progress=False)
    except Exception:
        return pd.DataFrame(columns=["Date", "Value"])
    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Value"])
    return df.reset_index()[["Date", "Close"]].rename(columns={"Close": "Value"})


def download_sp500(dates: pd.Series, baseline: float) -> pd.DataFrame:
    """Return S&P 500 values aligned to ``dates`` and normalised."""
    if dates.empty:
        return pd.DataFrame(columns=["Date", "SPX Value"])
    series = _download_sp500_series(dates.min(), dates.max())
    aligned = _align_to_dates(series, dates)
    norm = _normalize_to_start(aligned, baseline)
    return pd.DataFrame({"Date": dates, "SPX Value": norm.values})


# ---------------------------------------------------------------------------
# Public API used by the Streamlit app
# ---------------------------------------------------------------------------


def prepare_performance_dataframe(
    portfolio_csv: Path,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    baseline: float = 100.0,
) -> pd.DataFrame:
    """Return DataFrame with columns Date, Portfolio, S&P 500."""
    totals = load_portfolio_details(start_date, end_date, portfolio_csv=portfolio_csv)
    norm_port = totals.copy()
    norm_port["Total Equity"] = _normalize_to_start(norm_port["Total Equity"], baseline)
    spx = download_sp500(norm_port["Date"], baseline)
    return pd.DataFrame(
        {
            "Date": norm_port["Date"],
            "Portfolio": norm_port["Total Equity"],
            "S&P 500": spx["SPX Value"],
        }
    )


def build_plotly_figure(df: pd.DataFrame, baseline: float) -> "plotly.graph_objs._figure.Figure":
    """Create an interactive Plotly figure from ``df``."""
    return px.line(df, x="Date", y=["Portfolio", "S&P 500"], title=f"ChatGPT Portfolio vs. S&P 500 (start={baseline:g})")


def plot_comparison(df: pd.DataFrame, baseline: float, output: Optional[Path] = None) -> None:
    """Plot comparison using matplotlib, saving to ``output`` if provided."""
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["Date"], df["Portfolio"], label="Portfolio", marker="o")
    ax.plot(df["Date"], df["S&P 500"], label="S&P 500", linestyle="--", marker="o")

    ax.set_title(f"Portfolio vs. S&P 500 (start={baseline:g})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Index")
    ax.legend()
    fig.autofmt_xdate()
    plt.tight_layout()
    if output:
        output = output if output.is_absolute() else DATA_DIR / output
        plt.savefig(output, bbox_inches="tight")
    else:  # pragma: no cover - interactive
        plt.show()
    plt.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Plot portfolio performance vs S&P 500")
    parser.add_argument("--start-date", type=str, help="YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, help="YYYY-MM-DD")
    parser.add_argument(
        "--start-equity", type=float, default=100.0, help="Baseline to index both series (default 100)"
    )
    parser.add_argument("--portfolio", type=str, default=str(PORTFOLIO_CSV), help="Portfolio CSV path")
    parser.add_argument("--output", type=str, help="Optional path to save the chart (.png/.jpg/.pdf)")

    args = parser.parse_args()
    start = parse_date(args.start_date, "start date") if args.start_date else None
    end = parse_date(args.end_date, "end date") if args.end_date else None
    df = prepare_performance_dataframe(Path(args.portfolio), start, end, args.start_equity)
    out_path = Path(args.output) if args.output else None
    plot_comparison(df, args.start_equity, out_path)


if __name__ == "__main__":  # pragma: no cover - manual invocation
    _cli()
