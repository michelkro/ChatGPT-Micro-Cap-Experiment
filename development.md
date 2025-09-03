# Development Notes

This document records major enhancements added while modernizing the ChatGPT Micro‑Cap Experiment.

## Architecture & Infrastructure
- Introduced a Streamlit web interface with sidebar configuration and tabbed views for portfolio state, trade queue, performance and history.
- Added download buttons for portfolio snapshots and trade logs plus an interactive Plotly chart benchmarking against the S&P 500.
- Declared Streamlit and Plotly as dependencies and bundled them in `requirements.txt`.

## Trading Engine Improvements
- Centralized market‑data access with a Yahoo Finance primary source and Stooq fallback.
- Implemented an in‑memory cache so repeated price requests reuse previous results, minimizing network traffic.
- Added `apply_manual_trades` and routed `process_portfolio` through it, allowing scripted execution of queued orders.
- Exposed a `manual_trades` parameter and a market‑on‑open buy helper to simplify automated runs.

## LLM Integration
- Connected to OpenAI's API to request trade recommendations and parse them into actionable orders.
- Extended the Streamlit UI with an API‑key field, a "Generate Trades" button and raw LLM response display.

## Miscellaneous
- Created a `load_trade_log` helper to surface historic orders in the app.
- Updated `.gitignore` to ignore Python bytecode and `__pycache__` directories.

These changes transform the original experiment scripts into a reusable framework for daily LLM‑assisted trading.
