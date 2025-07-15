# QUANTO.trade Market-Making Bot

A sophisticated cryptocurrency market-making bot for OXFUN exchange that dynamically selects profitable trading pairs and executes market-making strategies.

## 🚀 Features

- **Dynamic Coin Selection**: Automatically selects up to 7 most profitable coins based on spread and volume
- **Real-time Market Data**: WebSocket connection for live price feeds and position updates
- **Smart Order Management**: Places orders 1 tick inside the spread when conditions are met
- **Position Awareness**: Automatically places closing orders when holding positions
- **Risk Management**: Built-in spread thresholds and distance checks from index prices
- **Multi-coin Trading**: Simultaneously trades multiple cryptocurrency pairs

## ⚠️ Risk Warning

**This bot places REAL orders with REAL money on OXFUN exchange. Use at your own risk!**

## 📁 Project Structure

```
├── ox_dynamic_websocket_.py    # WebSocket client for real-time data
├── ox_marketmaker_.py          # Main market-making bot
├── market_data_dynamic.json    # Real-time market data (auto-generated)
└── README.md                   # This file
```

## 🛠 Setup

### Prerequisites
- Python 3.8+
- OXFUN exchange account with API credentials
- Required packages: `websockets`, `requests`

### Installation

1. Clone the repository
```bash
git clone <repository-url>
cd oxfun-marketmaker
```

2. Install dependencies
```bash
pip install websockets requests
```

3. Configure API credentials in both files:
```python
# In ox_dynamic_websocket_.py and ox_marketmaker_.py
self.api_key = "YOUR_API_KEY"
self.api_secret = "YOUR_API_SECRET"
```

## 🎯 Trading Strategy

### Entry Conditions
- Minimum spread: **0.6%** between bid/ask
- Minimum distance from index price: **0.4%**
- Order size: **$5.50** worth per order
- Maximum coins traded: **7 simultaneously**

### Order Placement
- **Buy orders**: 1 tick above current best bid
- **Sell orders**: 1 tick below current best ask
- **Position closing**: At market when holding positions

### Risk Controls
- Auto-cancels orders when spread drops below 0.6%
- Prevents multiple orders on same side
- Prioritizes coins with existing positions
- 5-second order check intervals

## 🚀 Usage

### Step 1: Start WebSocket Data Feed
```bash
python ox_dynamic_websocket_.py
```
This connects to OXFUN WebSocket and generates `market_data_dynamic.json` with real-time data.

### Step 2: Start Market-Making Bot
```bash
python ox_marketmaker_.py
```
This reads the market data and executes trading strategy.

## ⚙️ Configuration

Adjust settings in `ox_marketmaker_.py`:

```python
maker.config.update({
    "min_spread_threshold": 0.006,      # 0.6% minimum spread
    "min_distance_from_index": 0.004,   # 0.4% from index price
    "order_value_usd": 5.5,             # $5.50 per order
    "tick_size": 0.001,                 # 0.1% tick size
    "order_check_interval": 5,          # 5 second intervals
})
```

## 📊 Monitored Coins

Currently supports these OXFUN markets:
- TITCOIN-USD-SWAP-LIN
- MOVE-USD-SWAP-LIN
- ZRO-USD-SWAP-LIN
- DOGEAI-USD-SWAP-LIN
- IO-USD-SWAP-LIN
- gork-USD-SWAP-LIN
- MEW-USD-SWAP-LIN
- NPC-USD-SWAP-LIN
- TROLL-USD-SWAP-LIN
- USDUC-USD-SWAP-LIN
- BANANABSC-USD-SWAP-LIN
- ENA-USD-SWAP-LIN
- CHILLGUY-USD-SWAP-LIN

## 🛑 Emergency Stop

Press `Ctrl+C` to safely stop the bot. It will automatically cancel all open orders before shutting down.

## 📈 Performance Monitoring

The bot provides real-time console output showing:
- Selected coins and their spreads
- Order placement/cancellation activities  
- Position status
- Market-making eligibility for each coin

## 🔧 Troubleshooting

- Ensure WebSocket client is running before starting the market maker
- Check API credentials and permissions
- Verify `market_data_dynamic.json` is being updated
- Monitor console logs for error messages

## 📄 License

Use at your own risk. Not financial advice.

---

**Happy Trading! 🎯**