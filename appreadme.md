# Streamlit App Guide

This app lets you reproduce the ChatGPT Micro‑Cap experiment in a web interface.

## 1. Installation
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Launch
```bash
streamlit run app.py
```

## 3. Using the App
1. **Load Portfolio** – Browse to your `chatgpt_portfolio_update.csv` (defaults to `Start Your Own/`).
2. **Provide API Key** – Enter an OpenAI key to enable LLM trade generation.
3. **Generate Trades** – Click *Generate Trades* to request suggestions; review and edit the queue.
4. **Run Daily Update** – Executes queued orders, updates prices and cash, and logs results.
5. **Download Results** – Grab updated portfolio and trade log CSVs from the sidebar.
6. **Performance Tab** – View an indexed equity curve versus the S&P 500.
7. **History Tab** – Inspect past executions via the trade log.

## 4. Data Files
- Portfolio updates and trade logs are saved alongside the source CSV by default.
- The app uses Yahoo Finance data with a Stooq fallback and caches prices for efficiency.

## 5. Tips
- Runs on any trading day; use the `ASOF_DATE` parameter in code for historical backfills.
- Manual orders can be entered or edited before running the update.

Enjoy experimenting!
