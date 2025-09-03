"""Streamlit dashboard for the ChatGPT Micro‑Cap experiment.

The goal of this app is to mirror the workflow used in the original
experiment where an LLM made daily trade decisions based on a portfolio
summary. Users can load their portfolio CSV, request trade proposals from
OpenAI, review/modify the suggestions, and then run the daily update to
apply them. A performance chart comparing the portfolio to the S&P 500 is
also included. The sidebar exposes configuration options, including a
utility to clear cached price data used by the trading engine.
"""

from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from openai import OpenAI, APIError

import generate_graph as gg

from trading_script import (
    load_latest_portfolio_state,
    process_portfolio,
    daily_results,
    load_trade_log,
    set_data_dir,
    set_alphavantage_key,
    clear_price_cache,
)

# ------------------------------
# Helpers
# ------------------------------

DEFAULT_PORTFOLIO = "Start Your Own/chatgpt_portfolio_update.csv"


def get_portfolio_summary(portfolio: pd.DataFrame, cash: float) -> str:
    """Return the string produced by :func:`daily_results` for LLM input."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        daily_results(portfolio, cash)
    return buf.getvalue()


def llm_propose_trades(summary: str, api_key: str) -> tuple[list[dict[str, Any]], str]:
    """Call OpenAI to propose trades.

    Parameters
    ----------
    summary:
        Textual summary of current portfolio produced by ``get_portfolio_summary``.
    api_key:
        API key used to authenticate with OpenAI.

    Returns
    -------
    trades, raw_text: tuple
        ``trades`` is a list of dictionaries suitable for ``process_portfolio``.
        ``raw_text`` is the unparsed LLM response shown for transparency.
    """
    client = OpenAI(api_key=api_key)
    prompt = (
        "You are an automated trading assistant.\n"
        "Given the portfolio summary below, decide what trades to execute "
        "today. Respond *only* with a JSON array. Each object must contain "
        "the fields: action ('buy' or 'sell'), ticker, shares, and optional "
        "stop_loss (for buys) or price (for sells).\n\n"
        f"{summary}\n"
    )

    try:
        response = client.responses.create(model="gpt-4.1-mini", input=prompt, temperature=0)
        raw = response.output_text.strip()
    except APIError as exc:  # pragma: no cover - network failure is hard to test
        return [], f"OpenAI API error: {exc}"

    # Attempt to parse JSON output. If parsing fails we return the raw text.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "trades" in parsed:
            parsed = parsed["trades"]
        if not isinstance(parsed, Iterable):
            raise ValueError
        trades = []
        for t in parsed:
            action = str(t.get("action", "")).lower()
            ticker = str(t.get("ticker", "")).upper()
            shares = float(t.get("shares", 0))
            trade: dict[str, Any] = {"action": action, "ticker": ticker, "shares": shares}
            if action == "buy" and "stop_loss" in t:
                trade["stop_loss"] = float(t["stop_loss"])
            if action == "sell" and "price" in t:
                trade["price"] = float(t["price"])
            trades.append(trade)
        return trades, raw
    except Exception:
        return [], raw


# ------------------------------
# Streamlit UI
# ------------------------------

st.set_page_config(page_title="ChatGPT Micro-Cap Experiment", layout="wide")
st.title("ChatGPT Micro-Cap Experiment")

if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = []
    st.session_state["cash"] = 0.0
    st.session_state["manual_trades"] = []
    st.session_state["portfolio_file"] = DEFAULT_PORTFOLIO
    st.session_state["llm_raw"] = ""
    st.session_state["openai_api_key"] = ""
    st.session_state["alpha_api_key"] = os.environ.get("ALPHAVANTAGE_API_KEY", "")

if st.session_state.get("alpha_api_key"):
    set_alphavantage_key(st.session_state["alpha_api_key"])

with st.sidebar:
    st.header("Configuration")
    portfolio_file = st.text_input("Portfolio CSV path", st.session_state["portfolio_file"])
    st.session_state["portfolio_file"] = portfolio_file
    api_key_input = st.text_input(
        "OpenAI API Key", type="password", value=st.session_state.get("openai_api_key", "")
    )
    if api_key_input:
        st.session_state["openai_api_key"] = api_key_input
    alpha_key_input = st.text_input(
        "Alpha Vantage API Key", type="password", value=st.session_state.get("alpha_api_key", "")
    )
    if alpha_key_input:
        st.session_state["alpha_api_key"] = alpha_key_input
        set_alphavantage_key(alpha_key_input)
    if st.button("Clear Price Cache"):
        clear_price_cache()
        st.success("Price cache cleared")
    if st.button("Load Portfolio"):
        file_path = Path(portfolio_file)
        if file_path.exists():
            set_data_dir(file_path.parent)
            pf, cash = load_latest_portfolio_state(str(file_path))
            st.session_state["portfolio"] = pf
            st.session_state["cash"] = cash
            st.success("Portfolio loaded")
        else:
            st.error("Portfolio file not found.")

if st.session_state["portfolio"]:
    tabs = st.tabs(["Portfolio", "Trades", "Performance", "History"])

    # Portfolio tab
    with tabs[0]:
        port_df = pd.DataFrame(st.session_state["portfolio"])
        st.subheader("Current Holdings")
        st.dataframe(port_df, use_container_width=True)
        st.metric("Cash balance", f"${st.session_state['cash']:.2f}")

    # Trades tab
    with tabs[1]:
        port_df = pd.DataFrame(st.session_state["portfolio"])
        st.subheader("Trade Suggestions via OpenAI")
        if st.button("Generate LLM Trades"):
            api_key = st.session_state.get("openai_api_key")
            if not api_key:
                st.error("Enter your OpenAI API key in the sidebar to request trades.")
            else:
                summary = get_portfolio_summary(port_df, st.session_state["cash"])
                trades, raw = llm_propose_trades(summary, api_key)
                st.session_state["manual_trades"].extend(trades)
                st.session_state["llm_raw"] = raw
        if st.session_state.get("llm_raw"):
            st.text_area("LLM raw response", st.session_state["llm_raw"], height=200)

        st.subheader("Log Manual Trades")
        with st.form("trade_form"):
            action = st.selectbox("Action", ["Buy", "Sell"])
            ticker = st.text_input("Ticker").upper()
            shares = st.number_input("Shares", min_value=0.0, step=1.0)
            stop_loss = price = 0.0
            if action == "Buy":
                stop_loss = st.number_input("Stop Loss", min_value=0.0, step=0.01, value=0.0)
            else:
                price = st.number_input("Sell Limit Price", min_value=0.0, step=0.01)
            submitted = st.form_submit_button("Add Trade")
        if submitted and ticker and shares > 0:
            trade = {"action": action.lower(), "ticker": ticker, "shares": shares}
            if action == "Buy":
                trade["stop_loss"] = stop_loss
            else:
                trade["price"] = price
            st.session_state["manual_trades"].append(trade)
            st.success("Trade added")

        if st.session_state["manual_trades"]:
            st.write("Pending trades (editable):")
            trades_df = pd.DataFrame(st.session_state["manual_trades"])
            edited = st.data_editor(trades_df, num_rows="dynamic")
            st.session_state["manual_trades"] = (
                edited.dropna(subset=["ticker"]).to_dict(orient="records")
            )
            if st.button("Clear Pending Trades"):
                st.session_state["manual_trades"] = []

        if st.button("Run Daily Update"):
            portfolio_df = pd.DataFrame(st.session_state["portfolio"])
            cash = st.session_state["cash"]
            trades = st.session_state.get("manual_trades", [])
            portfolio_df, cash = process_portfolio(
                portfolio_df, cash, manual_trades=trades, interactive=False
            )
            report = get_portfolio_summary(portfolio_df, cash)
            st.session_state["portfolio"] = portfolio_df.to_dict(orient="records")
            st.session_state["cash"] = cash
            st.session_state["manual_trades"] = []
            st.session_state["llm_raw"] = ""
            st.text(report)

            port_path = Path(st.session_state["portfolio_file"])
            if port_path.exists():
                st.download_button(
                    "Download Updated Portfolio",
                    port_path.read_text(),
                    file_name=port_path.name,
                )
            trade_log_path = port_path.parent / "chatgpt_trade_log.csv"
            trade_log_df = load_trade_log(trade_log_path)
            if not trade_log_df.empty:
                st.download_button(
                    "Download Trade Log",
                    trade_log_df.to_csv(index=False),
                    file_name=trade_log_path.name,
                )

    # Performance tab
    with tabs[2]:
        st.subheader("Performance Graph")
        start_str = st.text_input("Start Date (YYYY-MM-DD)", "")
        end_str = st.text_input("End Date (YYYY-MM-DD)", "")
        baseline = st.number_input("Baseline Equity", value=100.0)
        if st.button("Generate Graph"):
            start = pd.to_datetime(start_str) if start_str else None
            end = pd.to_datetime(end_str) if end_str else None
            chart_df = gg.prepare_performance_dataframe(
                Path(st.session_state["portfolio_file"]), start, end, baseline
            )
            if chart_df.empty:
                st.warning("No data available for selected range.")
            else:
                fig = gg.build_plotly_figure(chart_df, baseline)
                st.plotly_chart(fig, use_container_width=True)
                st.download_button(
                    "Download Data",
                    chart_df.to_csv(index=False),
                    file_name="performance.csv",
                )

    # History tab
    with tabs[3]:
        trade_log_path = Path(st.session_state["portfolio_file"]).parent / "chatgpt_trade_log.csv"
        log_df = load_trade_log(trade_log_path)
        if log_df.empty:
            st.write("Trade log is empty.")
        else:
            st.dataframe(log_df, use_container_width=True)
            st.download_button(
                "Download Trade Log",
                log_df.to_csv(index=False),
                file_name=trade_log_path.name,
            )
else:
    st.info("Use the sidebar to load a portfolio and begin.")
