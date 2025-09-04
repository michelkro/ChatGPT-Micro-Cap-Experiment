"""Enhanced Streamlit dashboard for the ChatGPT Micro‑Cap experiment.

This comprehensive web interface provides:
- Portfolio management with file upload/download capabilities
- LLM-powered trade generation and manual trade entry
- Performance visualization with S&P 500 benchmarking  
- Historical trade analysis and reporting
- Configuration management and API key handling
- Real-time portfolio updates and cash management

Features include drag-and-drop portfolio uploads, enhanced trade editing,
interactive performance charts, and comprehensive error handling.
"""

from __future__ import annotations

import io
import json
import os
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Iterable
from datetime import datetime

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

def create_new_portfolio() -> pd.DataFrame:
    """Create a new empty portfolio template."""
    return pd.DataFrame(columns=['ticker', 'shares', 'avg_cost', 'current_price', 'market_value', 'pnl'])

def validate_portfolio_file(uploaded_file) -> tuple[bool, str]:
    """Validate uploaded portfolio file format."""
    try:
        df = pd.read_csv(uploaded_file)
        required_columns = ['ticker', 'shares']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"
        
        if df.empty:
            return False, "Portfolio file is empty"
            
        return True, "Valid portfolio file"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def format_currency(amount: float) -> str:
    """Format currency with proper styling."""
    if amount >= 0:
        return f"${amount:,.2f}"
    else:
        return f"-${abs(amount):,.2f}"

def format_percentage(value: float) -> str:
    """Format percentage with color coding."""
    return f"{value:+.2f}%"

def safe_api_call(func, *args, **kwargs):
    """Wrapper for API calls with error handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None


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

st.set_page_config(
    page_title="ChatGPT Micro-Cap Experiment",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        padding: 1rem 0;
        border-bottom: 2px solid #f0f2f6;
        margin-bottom: 1rem;
    }
    .metric-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .trade-success {
        background: #d4edda;
        color: #155724;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border: 1px solid #c3e6cb;
    }
    .trade-warning {
        background: #fff3cd;
        color: #856404;
        padding: 0.5rem;
        border-radius: 0.25rem;
        border: 1px solid #ffeaa7;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.title("📈 ChatGPT Micro-Cap Trading Experiment")
st.markdown("**AI-Powered Portfolio Management Dashboard**")
st.markdown('</div>', unsafe_allow_html=True)

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
    st.header("⚙️ Configuration")
    
    # Portfolio Management Section
    st.subheader("📁 Portfolio Management")
    
    # File upload option
    uploaded_file = st.file_uploader(
        "Upload Portfolio CSV", 
        type=['csv'], 
        help="Upload a CSV file with your portfolio data"
    )
    
    if uploaded_file is not None:
        is_valid, message = validate_portfolio_file(uploaded_file)
        if is_valid:
            st.success(f"✅ {message}")
            if st.button("Load Uploaded Portfolio"):
                try:
                    df = pd.read_csv(uploaded_file)
                    st.session_state["portfolio"] = df.to_dict(orient="records")
                    st.session_state["cash"] = 10000.0  # Default cash amount
                    st.success("Portfolio loaded from upload!")
                except Exception as e:
                    st.error(f"Error loading portfolio: {str(e)}")
        else:
            st.error(f"❌ {message}")
    
    st.markdown("---")
    
    # File path option
    portfolio_file = st.text_input(
        "Or use Portfolio CSV path", 
        st.session_state["portfolio_file"],
        help="Path to your existing portfolio CSV file"
    )
    st.session_state["portfolio_file"] = portfolio_file
    
    if st.button("Load from Path"):
        file_path = Path(portfolio_file)
        if file_path.exists():
            try:
                set_data_dir(file_path.parent)
                pf, cash = load_latest_portfolio_state(str(file_path))
                st.session_state["portfolio"] = pf
                st.session_state["cash"] = cash
                st.success("✅ Portfolio loaded from path")
            except Exception as e:
                st.error(f"Error loading portfolio: {str(e)}")
        else:
            st.error("❌ Portfolio file not found")
    
    # Create new portfolio
    if st.button("Create New Portfolio"):
        st.session_state["portfolio"] = create_new_portfolio().to_dict(orient="records")
        st.session_state["cash"] = 10000.0
        st.success("✅ New portfolio created with $10,000 cash")
    
    st.markdown("---")
    st.subheader("🔑 API Configuration")
    
    api_key_input = st.text_input(
        "OpenAI API Key", 
        type="password", 
        value=st.session_state.get("openai_api_key", ""),
        help="Required for AI trade generation"
    )
    if api_key_input:
        st.session_state["openai_api_key"] = api_key_input
    
    alpha_key_input = st.text_input(
        "Alpha Vantage API Key", 
        type="password", 
        value=st.session_state.get("alpha_api_key", ""),
        help="Fallback data source (optional)"
    )
    if alpha_key_input:
        st.session_state["alpha_api_key"] = alpha_key_input
        set_alphavantage_key(alpha_key_input)
    
    st.markdown("---")
    st.subheader("🔧 System Controls")
    
    if st.button("🗑️ Clear Price Cache"):
        clear_price_cache()
        st.success("Price cache cleared")
    
    # System status
    if st.session_state.get("openai_api_key"):
        st.success("🤖 OpenAI Connected")
    else:
        st.warning("🤖 OpenAI Not Connected")
    
    if st.session_state.get("alpha_api_key"):
        st.success("📊 Alpha Vantage Connected")
    else:
        st.info("📊 Alpha Vantage Not Connected")

if st.session_state["portfolio"]:
    tabs = st.tabs(["📊 Portfolio", "💰 Trades", "📈 Performance", "📋 History"])

    # Portfolio tab
    with tabs[0]:
        port_df = pd.DataFrame(st.session_state["portfolio"])
        
        # Portfolio Summary
        col1, col2, col3, col4 = st.columns(4)
        
        total_value = 0
        if not port_df.empty and 'market_value' in port_df.columns:
            total_value = port_df['market_value'].sum()
        
        portfolio_total = total_value + st.session_state['cash']
        
        with col1:
            st.metric(
                "💰 Cash Balance", 
                format_currency(st.session_state['cash'])
            )
        
        with col2:
            st.metric(
                "📊 Holdings Value", 
                format_currency(total_value)
            )
        
        with col3:
            st.metric(
                "💼 Portfolio Total", 
                format_currency(portfolio_total)
            )
        
        with col4:
            positions_count = len(port_df) if not port_df.empty else 0
            st.metric("🎯 Positions", positions_count)
        
        st.markdown("---")
        
        if not port_df.empty:
            st.subheader("Current Holdings")
            
            # Enhanced portfolio display
            display_df = port_df.copy()
            
            # Format numeric columns
            if 'current_price' in display_df.columns:
                display_df['current_price'] = display_df['current_price'].apply(lambda x: f"${x:.2f}")
            if 'avg_cost' in display_df.columns:
                display_df['avg_cost'] = display_df['avg_cost'].apply(lambda x: f"${x:.2f}")
            if 'market_value' in display_df.columns:
                display_df['market_value'] = display_df['market_value'].apply(lambda x: f"${x:,.2f}")
            if 'pnl' in display_df.columns:
                display_df['pnl'] = display_df['pnl'].apply(lambda x: f"${x:+,.2f}")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "ticker": st.column_config.TextColumn("Ticker", width="small"),
                    "shares": st.column_config.NumberColumn("Shares", format="%.0f"),
                    "current_price": st.column_config.TextColumn("Current Price"),
                    "avg_cost": st.column_config.TextColumn("Avg Cost"),
                    "market_value": st.column_config.TextColumn("Market Value"),
                    "pnl": st.column_config.TextColumn("P&L")
                }
            )
            
            # Portfolio composition chart
            if 'market_value' in port_df.columns and port_df['market_value'].sum() > 0:
                st.subheader("Portfolio Composition")
                
                # Create pie chart data
                chart_data = port_df[['ticker', 'market_value']].copy()
                chart_data = chart_data[chart_data['market_value'] > 0]
                
                if not chart_data.empty:
                    import plotly.express as px
                    fig = px.pie(
                        chart_data, 
                        values='market_value', 
                        names='ticker',
                        title="Holdings Distribution"
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📝 No holdings in portfolio. Use the sidebar to load a portfolio or create a new one.")

    # Trades tab
    with tabs[1]:
        port_df = pd.DataFrame(st.session_state["portfolio"])
        
        # AI Trade Generation Section
        st.subheader("🤖 AI Trade Suggestions")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🧠 Generate AI Trades", type="primary"):
                api_key = st.session_state.get("openai_api_key")
                if not api_key:
                    st.error("⚠️ Enter your OpenAI API key in the sidebar to request trades.")
                else:
                    with st.spinner("🔄 AI is analyzing your portfolio..."):
                        try:
                            summary = get_portfolio_summary(port_df, st.session_state["cash"])
                            trades, raw = llm_propose_trades(summary, api_key)
                            if trades:
                                st.session_state["manual_trades"].extend(trades)
                                st.success(f"✅ AI generated {len(trades)} trade suggestions!")
                            else:
                                st.warning("🤖 AI didn't suggest any trades at this time.")
                            st.session_state["llm_raw"] = raw
                        except Exception as e:
                            st.error(f"❌ Error generating AI trades: {str(e)}")
        
        with col2:
            if st.session_state.get("llm_raw"):
                with st.expander("🔍 View AI Raw Response"):
                    st.text_area("", st.session_state["llm_raw"], height=150, key="ai_response")

        st.markdown("---")
        
        # Manual Trade Entry
        st.subheader("✋ Manual Trade Entry")
        
        with st.form("trade_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                action = st.selectbox("Action", ["Buy", "Sell"])
                ticker = st.text_input("Ticker Symbol").upper()
            
            with col2:
                shares = st.number_input("Number of Shares", min_value=0.1, step=1.0, value=1.0)
                if action == "Buy":
                    stop_loss = st.number_input("Stop Loss ($)", min_value=0.0, step=0.01, value=0.0)
                else:
                    price = st.number_input("Limit Price ($)", min_value=0.0, step=0.01, value=0.0)
            
            with col3:
                st.write("")  # Spacing
                submitted = st.form_submit_button("➕ Add Trade", type="primary")
                
        if submitted and ticker and shares > 0:
            trade = {"action": action.lower(), "ticker": ticker, "shares": shares}
            if action == "Buy" and 'stop_loss' in locals():
                trade["stop_loss"] = stop_loss
            elif action == "Sell" and 'price' in locals():
                trade["price"] = price
            st.session_state["manual_trades"].append(trade)
            st.success(f"✅ {action} order for {shares} shares of {ticker} added!")

        st.markdown("---")
        
        # Pending Trades Management
        if st.session_state["manual_trades"]:
            st.subheader("📋 Pending Trades")
            
            trades_df = pd.DataFrame(st.session_state["manual_trades"])
            
            # Display trade summary
            buy_trades = len([t for t in st.session_state["manual_trades"] if t.get("action") == "buy"])
            sell_trades = len([t for t in st.session_state["manual_trades"] if t.get("action") == "sell"])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📈 Buy Orders", buy_trades)
            with col2:
                st.metric("📉 Sell Orders", sell_trades) 
            with col3:
                st.metric("📊 Total Trades", len(st.session_state["manual_trades"]))
            
            # Editable trades table
            st.write("**Edit your pending trades:**")
            edited = st.data_editor(
                trades_df, 
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "action": st.column_config.SelectboxColumn(
                        "Action",
                        options=["buy", "sell"]
                    ),
                    "ticker": st.column_config.TextColumn("Ticker"),
                    "shares": st.column_config.NumberColumn("Shares", min_value=0),
                    "stop_loss": st.column_config.NumberColumn("Stop Loss", min_value=0),
                    "price": st.column_config.NumberColumn("Price", min_value=0)
                }
            )
            
            # Update session state
            st.session_state["manual_trades"] = (
                edited.dropna(subset=["ticker"]).to_dict(orient="records")
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Clear All Trades", type="secondary"):
                    st.session_state["manual_trades"] = []
                    st.rerun()
            with col2:
                trades_count = len(st.session_state["manual_trades"])
                st.write(f"**{trades_count} trade(s) ready for execution**")
        else:
            st.info("📝 No pending trades. Add trades manually or generate AI suggestions.")

        # Execute Trades Section
        st.markdown("---")
        st.subheader("🚀 Execute Trades")
        
        if st.session_state["manual_trades"]:
            st.warning(f"⚠️ You have {len(st.session_state['manual_trades'])} pending trades ready for execution.")
            
            if st.button("🚀 Execute All Trades", type="primary"):
                with st.spinner("⏳ Processing trades..."):
                    try:
                        portfolio_df = pd.DataFrame(st.session_state["portfolio"])
                        cash = st.session_state["cash"]
                        trades = st.session_state.get("manual_trades", [])
                        
                        # Process trades
                        portfolio_df, cash = process_portfolio(
                            portfolio_df, cash, manual_trades=trades, interactive=False
                        )
                        
                        # Generate report
                        report = get_portfolio_summary(portfolio_df, cash)
                        
                        # Update session state
                        st.session_state["portfolio"] = portfolio_df.to_dict(orient="records")
                        st.session_state["cash"] = cash
                        st.session_state["manual_trades"] = []
                        st.session_state["llm_raw"] = ""
                        
                        st.success("✅ All trades executed successfully!")
                        
                        # Show execution report
                        with st.expander("📊 Execution Report", expanded=True):
                            st.text(report)
                        
                        # Download options
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Portfolio download
                            portfolio_csv = portfolio_df.to_csv(index=False)
                            st.download_button(
                                "📥 Download Updated Portfolio",
                                portfolio_csv,
                                file_name=f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv"
                            )
                        
                        with col2:
                            # Trade log download
                            port_path = Path(st.session_state.get("portfolio_file", DEFAULT_PORTFOLIO))
                            trade_log_path = port_path.parent / "chatgpt_trade_log.csv"
                            
                            try:
                                trade_log_df = load_trade_log(trade_log_path)
                                if not trade_log_df.empty:
                                    st.download_button(
                                        "📥 Download Trade Log",
                                        trade_log_df.to_csv(index=False),
                                        file_name=f"trade_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                        mime="text/csv"
                                    )
                            except Exception as e:
                                st.warning(f"Trade log not available: {str(e)}")
                                
                    except Exception as e:
                        st.error(f"❌ Error executing trades: {str(e)}")
                        st.error("Please check your trades and try again.")
        else:
            st.info("📝 No trades to execute. Add some trades first.")

    # Performance tab
    with tabs[2]:
        st.subheader("📈 Performance Analytics")
        
        # Performance metrics row
        if st.session_state["portfolio"]:
            port_df = pd.DataFrame(st.session_state["portfolio"])
            total_value = 0
            total_pnl = 0
            
            if not port_df.empty:
                if 'market_value' in port_df.columns:
                    total_value = port_df['market_value'].sum()
                if 'pnl' in port_df.columns:
                    total_pnl = port_df['pnl'].sum()
            
            portfolio_total = total_value + st.session_state['cash']
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💼 Total Portfolio", format_currency(portfolio_total))
            with col2:
                st.metric("💰 Total P&L", format_currency(total_pnl))
            with col3:
                if portfolio_total > 0:
                    pnl_percent = (total_pnl / (portfolio_total - total_pnl)) * 100
                    st.metric("📊 Return %", f"{pnl_percent:+.2f}%")
                else:
                    st.metric("📊 Return %", "0.00%")
            with col4:
                winning_positions = len([p for p in st.session_state["portfolio"] 
                                       if p.get('pnl', 0) > 0]) if st.session_state["portfolio"] else 0
                st.metric("🎯 Winners", winning_positions)
        
        st.markdown("---")
        
        # Performance Chart Configuration
        st.subheader("🎯 Performance vs Benchmarks")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            start_str = st.date_input("Start Date", value=None, key="perf_start")
        with col2:
            end_str = st.date_input("End Date", value=None, key="perf_end")
        with col3:
            baseline = st.number_input("Baseline Equity", value=100.0, min_value=1.0)
        
        # Benchmark selection
        benchmark_options = ["SPY", "IWO", "XBI", "IWM", "QQQ", "VTI"]
        selected_benchmarks = st.multiselect(
            "Select Benchmarks", 
            benchmark_options, 
            default=["SPY", "IWO"],
            help="Choose benchmarks to compare against your portfolio"
        )
        
        if st.button("📊 Generate Performance Chart", type="primary"):
            try:
                with st.spinner("📈 Generating performance analysis..."):
                    start = pd.to_datetime(start_str) if start_str else None
                    end = pd.to_datetime(end_str) if end_str else None
                    
                    portfolio_path = Path(st.session_state.get("portfolio_file", DEFAULT_PORTFOLIO))
                    
                    if portfolio_path.exists():
                        chart_df = gg.prepare_performance_dataframe(portfolio_path, start, end, baseline)
                        
                        if chart_df.empty:
                            st.warning("📉 No performance data available for the selected date range.")
                        else:
                            # Create enhanced chart
                            fig = gg.build_plotly_figure(chart_df, baseline)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Performance statistics
                            st.subheader("📊 Performance Statistics")
                            
                            # Calculate key metrics if data available
                            if 'Portfolio' in chart_df.columns:
                                portfolio_return = ((chart_df['Portfolio'].iloc[-1] / chart_df['Portfolio'].iloc[0]) - 1) * 100
                                st.metric("Portfolio Return", f"{portfolio_return:+.2f}%")
                            
                            if 'S&P 500' in chart_df.columns:
                                sp500_return = ((chart_df['S&P 500'].iloc[-1] / chart_df['S&P 500'].iloc[0]) - 1) * 100
                                st.metric("S&P 500 Return", f"{sp500_return:+.2f}%")
                                
                                if 'Portfolio' in chart_df.columns:
                                    alpha = portfolio_return - sp500_return
                                    st.metric("Alpha vs S&P 500", f"{alpha:+.2f}%")
                            
                            # Download options
                            col1, col2 = st.columns(2)
                            with col1:
                                st.download_button(
                                    "📥 Download Performance Data",
                                    chart_df.to_csv(index=True),
                                    file_name=f"performance_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                    mime="text/csv"
                                )
                            with col2:
                                # Create summary report
                                summary_report = f"""Performance Summary Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Portfolio Performance:
- Total Return: {portfolio_return:+.2f}% (if data available)
- Period: {start_str} to {end_str}
- Baseline Value: {baseline}

Benchmark Comparison:
- S&P 500 Return: {sp500_return:+.2f}% (if available)
- Alpha: {alpha:+.2f}% (if available)

Data Points: {len(chart_df)} trading days
"""
                                st.download_button(
                                    "📄 Download Summary Report",
                                    summary_report,
                                    file_name=f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                                    mime="text/plain"
                                )
                    else:
                        st.error("❌ Portfolio file not found. Please load a portfolio first.")
                        
            except Exception as e:
                st.error(f"❌ Error generating performance chart: {str(e)}")
                st.error("Please check your portfolio file and date range.")
        
        # Additional performance tools
        with st.expander("🔧 Advanced Performance Tools"):
            st.write("**Risk Analysis** (Future Enhancement)")
            st.info("🚧 Sharpe ratio, maximum drawdown, and volatility analysis coming soon!")
            
            st.write("**Portfolio Optimization** (Future Enhancement)")  
            st.info("🚧 Mean reversion analysis and portfolio optimization tools coming soon!")

    # History tab
    with tabs[3]:
        st.subheader("📋 Trading History & Analytics")
        
        try:
            portfolio_file = st.session_state.get("portfolio_file", DEFAULT_PORTFOLIO)
            trade_log_path = Path(portfolio_file).parent / "chatgpt_trade_log.csv"
            
            log_df = load_trade_log(trade_log_path)
            
            if log_df.empty:
                st.info("📝 No trading history available yet. Execute some trades to see them here!")
            else:
                # Trading summary metrics
                col1, col2, col3, col4 = st.columns(4)
                
                total_trades = len(log_df)
                
                if 'action' in log_df.columns:
                    buy_trades = len(log_df[log_df['action'].str.lower() == 'buy'])
                    sell_trades = len(log_df[log_df['action'].str.lower() == 'sell'])
                else:
                    buy_trades = sell_trades = 0
                
                # Calculate total volume if price and shares columns exist
                total_volume = 0
                if 'price' in log_df.columns and 'shares' in log_df.columns:
                    log_df_clean = log_df.dropna(subset=['price', 'shares'])
                    if not log_df_clean.empty:
                        total_volume = (log_df_clean['price'] * log_df_clean['shares']).sum()
                
                with col1:
                    st.metric("📊 Total Trades", total_trades)
                with col2:
                    st.metric("📈 Buy Orders", buy_trades)
                with col3:
                    st.metric("📉 Sell Orders", sell_trades)
                with col4:
                    st.metric("💰 Total Volume", format_currency(total_volume))
                
                st.markdown("---")
                
                # Enhanced trade log display
                st.subheader("🕒 Complete Trade History")
                
                # Format dates if date column exists
                display_log = log_df.copy()
                if 'date' in display_log.columns:
                    display_log['date'] = pd.to_datetime(display_log['date']).dt.strftime('%Y-%m-%d')
                
                # Format currency columns
                currency_columns = ['price', 'total_cost', 'market_value']
                for col in currency_columns:
                    if col in display_log.columns:
                        display_log[col] = display_log[col].apply(lambda x: f"${x:.2f}" if pd.notnull(x) else "N/A")
                
                # Display with better formatting
                st.dataframe(
                    display_log,
                    use_container_width=True,
                    column_config={
                        "date": st.column_config.TextColumn("Date", width="small"),
                        "action": st.column_config.TextColumn("Action", width="small"),
                        "ticker": st.column_config.TextColumn("Ticker", width="small"),
                        "shares": st.column_config.NumberColumn("Shares", format="%.0f"),
                        "price": st.column_config.TextColumn("Price"),
                        "total_cost": st.column_config.TextColumn("Total Cost")
                    }
                )
                
                # Trade analysis
                with st.expander("📊 Trade Analysis"):
                    if 'ticker' in log_df.columns:
                        # Most traded symbols
                        symbol_counts = log_df['ticker'].value_counts().head(10)
                        st.write("**Most Traded Symbols:**")
                        st.bar_chart(symbol_counts)
                    
                    if 'date' in log_df.columns:
                        # Trading activity over time
                        log_df['date'] = pd.to_datetime(log_df['date'])
                        daily_trades = log_df.groupby(log_df['date'].dt.date).size()
                        st.write("**Trading Activity Over Time:**")
                        st.line_chart(daily_trades)
                
                # Download options
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "📥 Download Trade Log",
                        log_df.to_csv(index=False),
                        file_name=f"trade_log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # Create trade summary report
                    trade_summary = f"""Trading Activity Summary
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Overall Statistics:
- Total Trades Executed: {total_trades}
- Buy Orders: {buy_trades}
- Sell Orders: {sell_trades}
- Total Volume Traded: {format_currency(total_volume)}

Recent Activity:
- Last Trade Date: {log_df['date'].max() if 'date' in log_df.columns else 'N/A'}
- Most Active Symbol: {symbol_counts.index[0] if 'ticker' in log_df.columns and not symbol_counts.empty else 'N/A'}

Portfolio Health:
- Active Positions: {len(st.session_state.get('portfolio', []))}
- Cash Balance: {format_currency(st.session_state.get('cash', 0))}

Note: This is an automated trading experiment using AI assistance.
All trades are executed according to the experimental protocol.
"""
                    st.download_button(
                        "📄 Download Trading Summary",
                        trade_summary,
                        file_name=f"trading_summary_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain"
                    )
                    
        except Exception as e:
            st.error(f"❌ Error loading trade history: {str(e)}")
            st.info("💡 Make sure you have executed some trades and have a valid portfolio file.")
else:
    # Welcome screen for new users
    st.markdown("""
    <div style="text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white; margin: 2rem 0;">
        <h1>🎯 Welcome to the ChatGPT Micro-Cap Experiment!</h1>
        <p style="font-size: 1.2em; margin: 1rem 0;">AI-powered portfolio management and trading analysis platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🚀 Getting Started")
        st.markdown("""
        **Choose one of these options to begin:**
        
        1. **📁 Upload Portfolio** - Drag and drop your existing CSV file
        2. **📂 Load from Path** - Enter the path to your portfolio file  
        3. **✨ Create New Portfolio** - Start fresh with $10,000 cash
        
        Use the sidebar controls to get started! →
        """)
        
        with st.expander("📋 Portfolio File Format"):
            st.markdown("""
            Your CSV file should contain these columns:
            - `ticker` - Stock symbol (e.g., AAPL, MSFT)
            - `shares` - Number of shares owned
            - `avg_cost` - Average cost per share (optional)
            - `current_price` - Current price per share (optional)
            - `market_value` - Current market value (optional)
            - `pnl` - Profit/Loss (optional)
            """)
            
            # Sample data
            sample_data = pd.DataFrame({
                'ticker': ['AAPL', 'GOOGL', 'MSFT'],
                'shares': [10, 5, 15],
                'avg_cost': [150.00, 2500.00, 300.00],
                'current_price': [175.00, 2600.00, 350.00],
                'market_value': [1750.00, 13000.00, 5250.00],
                'pnl': [250.00, 500.00, 750.00]
            })
            st.dataframe(sample_data, use_container_width=True)
    
    with col2:
        st.subheader("🤖 Platform Features")
        st.markdown("""
        **🧠 AI Trade Generation**
        - OpenAI-powered trade suggestions
        - Portfolio analysis and recommendations
        - Risk-aware position sizing
        
        **📊 Portfolio Management**  
        - Real-time portfolio tracking
        - P&L calculations and metrics
        - Position management tools
        
        **📈 Performance Analytics**
        - Benchmark comparisons (S&P 500, etc.)
        - Historical performance charts
        - Risk and return analysis
        
        **📋 Trade Execution & History**
        - Manual and AI trade entry
        - Complete trade logging
        - Execution reporting
        """)
        
        with st.expander("⚠️ Important Disclaimer"):
            st.warning("""
            **This is an experimental research platform.**
            
            - Not financial advice or investment guidance
            - Trades are simulated for research purposes
            - High-risk micro-cap securities focus
            - Results may not reflect real trading conditions
            
            Please read the full disclaimer in the README.md file.
            """)
    
    # Quick start actions
    st.markdown("---")
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🆕 Start with Demo Portfolio", type="primary"):
            # Create demo portfolio
            demo_portfolio = pd.DataFrame({
                'ticker': ['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
                'shares': [10, 15, 3, 5],
                'avg_cost': [150.0, 300.0, 2500.0, 3200.0],
                'current_price': [175.0, 350.0, 2600.0, 3300.0],
                'market_value': [1750.0, 5250.0, 7800.0, 16500.0],
                'pnl': [250.0, 750.0, 300.0, 500.0]
            })
            st.session_state["portfolio"] = demo_portfolio.to_dict(orient="records")
            st.session_state["cash"] = 5000.0
            st.success("✅ Demo portfolio created! Check the Portfolio tab.")
            st.rerun()
    
    with col2:
        if st.button("📖 View Sample Data"):
            st.info("Check the 'Start Your Own' folder for sample CSV files.")
            
    with col3:
        if st.button("🔧 System Status"):
            st.info("Check the sidebar for API connection status.")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 1rem;">
        <small>
        ChatGPT Micro-Cap Trading Experiment | 
        Built with Streamlit & OpenAI | 
        For Research & Educational Purposes Only
        </small>
    </div>
    """, unsafe_allow_html=True)
