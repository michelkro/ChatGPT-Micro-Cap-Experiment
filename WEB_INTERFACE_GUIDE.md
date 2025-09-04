# 📈 ChatGPT Micro-Cap Experiment - Web Interface Guide

## 🚀 Quick Start

### Option 1: Automated Launch (Recommended)
```bash
python3 launch.py
```
This script will automatically check dependencies, install missing packages, and start the web interface.

### Option 2: Manual Launch
```bash
# Install dependencies
pip3 install -r requirements.txt

# Launch the web app
streamlit run app.py
```

The web interface will open at `http://localhost:8501`

## 🎯 Features Overview

### 📊 Portfolio Management Tab
- **Portfolio Upload**: Drag-and-drop CSV files or load from file paths
- **Real-time Metrics**: Cash balance, holdings value, total portfolio value, and position count
- **Visual Analytics**: Portfolio composition pie charts and formatted holdings tables
- **Demo Portfolio**: Start with pre-loaded sample data

### 💰 Trades Tab  
- **AI Trade Generation**: OpenAI-powered trade suggestions with portfolio analysis
- **Manual Trade Entry**: Add buy/sell orders with stop-loss and limit price options
- **Trade Management**: Editable pending trades table with validation
- **Execution Engine**: Process all trades with detailed reporting and CSV downloads

### 📈 Performance Tab
- **Performance Metrics**: Real-time P&L, returns, and winning positions tracking
- **Benchmark Comparison**: Compare against S&P 500, IWO, XBI, IWM, QQQ, VTI
- **Interactive Charts**: Plotly-powered performance visualization
- **Data Export**: Download performance data and summary reports
- **Advanced Tools**: Risk analysis and portfolio optimization (coming soon)

### 📋 History Tab
- **Trade Analytics**: Complete trade history with volume and activity metrics
- **Visual Analysis**: Most traded symbols charts and activity over time
- **Comprehensive Reports**: Downloadable trading summaries and activity logs
- **Data Export**: CSV exports with formatted currency and date columns

## 🔧 Configuration

### Sidebar Controls
- **📁 Portfolio Management**: Upload, load, or create new portfolios
- **🔑 API Keys**: OpenAI and Alpha Vantage configuration
- **🔧 System Controls**: Price cache management and connection status

### API Keys Required
- **OpenAI API Key**: Required for AI trade generation
- **Alpha Vantage API Key**: Optional fallback for market data

## 📋 File Format Requirements

### Portfolio CSV Format
Required columns:
- `ticker` - Stock symbol (e.g., AAPL, MSFT)
- `shares` - Number of shares owned

Optional columns (auto-calculated if missing):
- `avg_cost` - Average cost per share
- `current_price` - Current market price
- `market_value` - Current position value
- `pnl` - Profit/Loss

### Example Portfolio CSV:
```csv
ticker,shares,avg_cost,current_price,market_value,pnl
AAPL,10,150.00,175.00,1750.00,250.00
GOOGL,5,2500.00,2600.00,13000.00,500.00
MSFT,15,300.00,350.00,5250.00,750.00
```

## 🎨 User Interface Features

### Enhanced Styling
- Modern gradient headers and custom CSS
- Color-coded metrics and status indicators  
- Responsive column layouts
- Interactive tabs with emoji icons
- Professional data tables with formatting

### Error Handling
- Comprehensive input validation
- Graceful error recovery
- User-friendly error messages
- API failure handling
- File format validation

### Data Export Options
- Portfolio snapshots with timestamps
- Trade logs and execution reports
- Performance data and benchmark comparisons
- Summary reports in multiple formats

## 🚧 Advanced Features (Coming Soon)

- **Risk Analysis**: Sharpe ratio, maximum drawdown, volatility metrics
- **Portfolio Optimization**: Mean reversion and optimization algorithms  
- **Real-time Data**: Live market data integration
- **Advanced Charts**: Candlestick charts and technical indicators
- **Backtesting Engine**: Historical strategy testing

## ⚠️ Important Notes

### Security
- API keys are stored in session state (not persistent)
- No sensitive data is logged or saved permanently
- All trades are simulated for research purposes

### Performance
- Price data is cached to reduce API calls
- Use "Clear Price Cache" if data seems stale
- Large portfolios may take longer to process

### Limitations
- This is an experimental research platform
- Not suitable for live trading
- Results may not reflect real market conditions
- Focus on micro-cap securities (high risk)

## 📞 Support

- Check the CLAUDE.md file for development guidance
- Review README.md for project background
- Ensure all dependencies are installed correctly
- Verify API keys are configured in the sidebar

---

**Built with Streamlit, OpenAI, and Yahoo Finance | For Research & Educational Purposes Only**