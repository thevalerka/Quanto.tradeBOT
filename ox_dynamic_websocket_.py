import asyncio
import websockets
import json
import logging
import time
import hmac
import base64
import hashlib
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# All available market codes to choose from
all_market_codes = ["TITCOIN-USD-SWAP-LIN","MOVE-USD-SWAP-LIN","ZRO-USD-SWAP-LIN","DOGEAI-USD-SWAP-LIN","IO-USD-SWAP-LIN","gork-USD-SWAP-LIN","MEW-USD-SWAP-LIN","NPC-USD-SWAP-LIN","TROLL-USD-SWAP-LIN","USDUC-USD-SWAP-LIN","BANANABSC-USD-SWAP-LIN","ENA-USD-SWAP-LIN","CHILLGUY-USD-SWAP-LIN"]

class OXDynamicWebSocketClient:
    def __init__(self, uri="wss://api.ox.fun/v2/websocket"):
        self.uri = uri
        self.websocket = None

        # API credentials
        self.api_key = ""
        self.api_secret = ""

        # Dynamic coin selection
        self.max_coins = 7
        self.min_spread_percent = 0.7
        self.selected_market_codes = []
        self.coins_with_positions = set()

        # Timing controls
        self.last_position_check = datetime.now()
        self.last_coin_update = datetime.now()
        self.position_check_interval = timedelta(minutes=1)
        self.coin_update_interval = timedelta(minutes=5)

        # Authentication state
        self.authenticated = False

        # Data store for all coins (not just selected ones)
        self.data_store = {}
        for market_code in all_market_codes:
            self.data_store[market_code] = {
                "bestAsk": None,
                "bestBid": None,
                "amountAsk": None,
                "amountBid": None,
                "markPrice": None,
                "indexPrice": None,
                "volume24h": None,
                "spread_perc": None,
                "last_updated": None
            }

    async def connect(self):
        """Connect to WebSocket"""
        try:
            self.websocket = await websockets.connect(self.uri)
            logger.info(f"Connected to {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def create_auth_message(self):
        """Create authentication message"""
        ts = str(int(time.time() * 1000))
        sig_payload = (ts + 'GET/auth/self/verify').encode('utf-8')
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode('utf-8'), sig_payload, hashlib.sha256).digest()
        ).decode('utf-8')

        return {
            "op": "login",
            "tag": 1,
            "data": {
                "apiKey": self.api_key,
                "timestamp": ts,
                "signature": signature
            }
        }

    async def authenticate(self):
        """Authenticate with the WebSocket"""
        try:
            auth_msg = self.create_auth_message()
            await self.websocket.send(json.dumps(auth_msg))
            logger.info("Sent authentication message")
        except Exception as e:
            logger.error(f"Failed to authenticate: {e}")

    async def subscribe_to_positions(self):
        """Subscribe to position updates"""
        position_subscription = {
            "op": "subscribe",
            "args": ["position:all"],
            "tag": 102
        }
        try:
            await self.websocket.send(json.dumps(position_subscription))
            logger.info("Subscribed to position updates")
        except Exception as e:
            logger.error(f"Failed to subscribe to positions: {e}")

    async def subscribe_to_all_tickers(self):
        """Subscribe to ticker data for all available coins"""
        ticker_args = [f"ticker:{market_code}" for market_code in all_market_codes]

        ticker_subscription = {
            "op": "subscribe",
            "tag": "all_tickers",
            "args": ticker_args
        }

        try:
            await self.websocket.send(json.dumps(ticker_subscription))
            logger.info(f"Subscribed to all tickers for coin selection")
        except Exception as e:
            logger.error(f"Failed to subscribe to all tickers: {e}")

    async def make_initial_selection(self):
        """Make initial coin selection to start getting data"""
        # Select first 7 coins as initial selection
        self.selected_market_codes = all_market_codes[:self.max_coins]
        logger.info(f"Initial coin selection: {self.selected_market_codes}")

        # Subscribe to bestBidAsk for initial selection
        await self.subscribe_to_selected_channels()

        # Save initial state
        self.save_to_json()

    async def subscribe_to_selected_channels(self):
        """Subscribe to bestBidAsk channels for selected market codes"""
        if not self.selected_market_codes:
            logger.warning("No coins selected for subscription")
            return

        # Build subscription args for selected coins only
        best_bid_ask_args = [f"bestBidAsk:{market_code}" for market_code in self.selected_market_codes]

        # Subscribe to bestBidAsk for selected coins
        bid_ask_subscription = {
            "op": "subscribe",
            "tag": "selected_bid_ask",
            "args": best_bid_ask_args
        }

        try:
            await self.websocket.send(json.dumps(bid_ask_subscription))
            logger.info(f"Subscribed to bestBidAsk for selected coins: {', '.join(self.selected_market_codes)}")
        except Exception as e:
            logger.error(f"Failed to send bestBidAsk subscriptions: {e}")

    async def unsubscribe_from_channels(self, market_codes):
        """Unsubscribe from bestBidAsk channels for given market codes"""
        if not market_codes:
            return

        best_bid_ask_args = [f"bestBidAsk:{market_code}" for market_code in market_codes]

        unsubscription = {
            "op": "unsubscribe",
            "tag": "unsubscribe_bid_ask",
            "args": best_bid_ask_args
        }

        try:
            await self.websocket.send(json.dumps(unsubscription))
            logger.info(f"Unsubscribed from bestBidAsk for: {', '.join(market_codes)}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe: {e}")

    def select_coins(self):
        """Select up to 7 coins based on spread and volume criteria"""
        # Get coins with sufficient data and spread > 0.7%
        eligible_coins = []

        for market_code, data in self.data_store.items():
            if (data["spread_perc"] is not None and
                data["volume24h"] is not None and
                data["spread_perc"] > self.min_spread_percent):

                eligible_coins.append({
                    "market_code": market_code,
                    "spread_perc": data["spread_perc"],
                    "volume24h": float(data["volume24h"]) if data["volume24h"] else 0
                })

        # Sort by volume24h in descending order
        eligible_coins.sort(key=lambda x: x["volume24h"], reverse=True)

        # Start with coins that have positions
        selected = list(self.coins_with_positions)

        # Add coins based on volume until we reach max_coins
        for coin in eligible_coins:
            if coin["market_code"] not in selected and len(selected) < self.max_coins:
                selected.append(coin["market_code"])

        # If we still don't have enough coins and there are coins with positions not in eligible_coins
        # (spread < 0.7%), we keep them anyway since they have positions
        previous_selected = set(self.selected_market_codes)
        new_selected = set(selected)

        self.selected_market_codes = selected

        logger.info(f"Selected coins: {selected}")
        logger.info(f"Coins with positions: {list(self.coins_with_positions)}")

        return previous_selected, new_selected

    async def update_coin_subscriptions(self):
        """Update subscriptions based on newly selected coins"""
        previous_selected, new_selected = self.select_coins()

        # Find coins to unsubscribe from
        to_unsubscribe = previous_selected - new_selected

        # Find coins to subscribe to
        to_subscribe = new_selected - previous_selected

        if to_unsubscribe:
            await self.unsubscribe_from_channels(list(to_unsubscribe))

        if to_subscribe:
            # Subscribe to new coins
            best_bid_ask_args = [f"bestBidAsk:{market_code}" for market_code in to_subscribe]

            bid_ask_subscription = {
                "op": "subscribe",
                "tag": "new_selected_bid_ask",
                "args": best_bid_ask_args
            }

            try:
                await self.websocket.send(json.dumps(bid_ask_subscription))
                logger.info(f"Subscribed to new coins: {', '.join(to_subscribe)}")
            except Exception as e:
                logger.error(f"Failed to subscribe to new coins: {e}")

    def process_best_bid_ask(self, data):
        """Process bestBidAsk data"""
        try:
            market_data = data.get("data", {})
            ask_data = market_data.get("ask", [])
            bid_data = market_data.get("bid", [])
            market_code = market_data.get("marketCode")

            if market_code and market_code in all_market_codes:
                bestAsk = 0
                bestBid = 0

                if ask_data and len(ask_data) >= 2:
                    self.data_store[market_code]["bestAsk"] = ask_data[0]
                    self.data_store[market_code]["amountAsk"] = ask_data[1]
                    bestAsk = ask_data[0]

                if bid_data and len(bid_data) >= 2:
                    self.data_store[market_code]["bestBid"] = bid_data[0]
                    self.data_store[market_code]["amountBid"] = bid_data[1]
                    bestBid = bid_data[0]

                if bestBid != 0 and bestAsk != 0:
                    self.data_store[market_code]["spread_perc"] = (bestAsk - bestBid) * 100 / bestBid

                self.data_store[market_code]["last_updated"] = datetime.now().isoformat()

                logger.info(f"Updated bestBidAsk for {market_code} - Ask: {self.data_store[market_code]['bestAsk']}, Bid: {self.data_store[market_code]['bestBid']}, Spread: {self.data_store[market_code]['spread_perc']:.3f}%")

        except Exception as e:
            logger.error(f"Error processing bestBidAsk data: {e}")

    def process_ticker(self, data):
        """Process ticker data"""
        try:
            ticker_data = data.get("data", [])
            updated_count = 0

            for item in ticker_data:
                market_code = item.get("marketCode")

                if market_code and market_code in all_market_codes:
                    self.data_store[market_code]["markPrice"] = item.get("markPrice")
                    self.data_store[market_code]["indexPrice"] = item.get("indexPrice")
                    self.data_store[market_code]["volume24h"] = item.get("volume24h")
                    self.data_store[market_code]["last_updated"] = datetime.now().isoformat()
                    updated_count += 1

                    logger.info(f"Updated ticker for {market_code} - Mark Price: {self.data_store[market_code]['markPrice']}, Volume24h: {self.data_store[market_code]['volume24h']}")

            # Save data after processing ticker updates
            if updated_count > 0:
                self.save_to_json()

        except Exception as e:
            logger.error(f"Error processing ticker data: {e}")

    def process_positions(self, data):
        """Process position data to identify coins with open positions"""
        try:
            positions_data = data.get("data", [])
            current_positions = set()

            for position in positions_data:
                market_code = position.get("marketCode")
                position_size = float(position.get("position", 0))

                if market_code and position_size != 0:
                    current_positions.add(market_code)
                    logger.info(f"Open position in {market_code}: {position_size}")

            # Only update if positions actually changed
            if current_positions != self.coins_with_positions:
                self.coins_with_positions = current_positions
                logger.info(f"Updated coins with positions: {list(current_positions)}")
                # Save when positions change
                self.save_to_json()

        except Exception as e:
            logger.error(f"Error processing position data: {e}")

    def save_to_json(self, filename="market_data_dynamic.json"):
        """Save current data to JSON file"""
        try:
            # Save data for selected coins if any, otherwise save all data
            if self.selected_market_codes:
                selected_data = {}
                for market_code in self.selected_market_codes:
                    selected_data[market_code] = self.data_store[market_code]
            else:
                # If no coins selected yet, save all available data
                selected_data = {k: v for k, v in self.data_store.items()
                               if v["last_updated"] is not None}

            output_data = {
                "selected_coins": self.selected_market_codes,
                "coins_with_positions": list(self.coins_with_positions),
                "total_coins_tracked": len(selected_data),
                "last_updated": datetime.now().isoformat(),
                "data": selected_data
            }

            with open(filename, 'w') as f:
                json.dump(output_data, f, indent=4)
            logger.info(f"Data saved to {filename} - {len(selected_data)} coins")

        except Exception as e:
            logger.error(f"Error saving to JSON: {e}")
            # Try to save to a backup location
            try:
                import os
                backup_filename = f"backup_{filename}"
                with open(backup_filename, 'w') as f:
                    json.dump({"error": str(e), "timestamp": datetime.now().isoformat()}, f)
                logger.info(f"Saved error info to {backup_filename}")
            except:
                logger.error("Could not save backup file either")

    async def handle_message(self, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)

            # Handle nonce for authentication
            if 'nonce' in data:
                await self.authenticate()
                return

            # Handle authentication response
            if 'event' in data and data['event'] == 'login':
                if data.get('success'):
                    logger.info("Authentication successful")
                    self.authenticated = True
                    await self.subscribe_to_positions()
                    await self.subscribe_to_all_tickers()

                    # Make initial coin selection with default coins
                    await self.make_initial_selection()
                else:
                    logger.error("Authentication failed")
                return

            # Handle subscription confirmations
            if data.get("success") and data.get("event") == "subscribe":
                logger.info(f"Successfully subscribed to {data.get('channel')}")
                return

            # Handle data updates
            table = data.get("table")

            if table == "bestBidAsk":
                self.process_best_bid_ask(data)
                self.save_to_json()

            elif table == "ticker":
                self.process_ticker(data)

            elif table == "position":
                self.process_positions(data)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def check_timers(self):
        """Check if it's time to update positions or coins"""
        now = datetime.now()

        # Check positions every minute
        if now - self.last_position_check >= self.position_check_interval:
            self.last_position_check = now
            logger.info("Position check timer triggered")
            # Save data periodically
            self.save_to_json()

        # Update coin selection every 5 minutes
        if now - self.last_coin_update >= self.coin_update_interval:
            self.last_coin_update = now
            logger.info("Coin update timer triggered")
            await self.update_coin_subscriptions()

    async def listen(self):
        """Listen for WebSocket messages"""
        try:
            while True:
                # Check timers
                await self.check_timers()

                # Wait for message with timeout
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    await self.handle_message(message)
                except asyncio.TimeoutError:
                    # Timeout is normal, just continue to check timers
                    continue

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in listen loop: {e}")

    async def run(self):
        """Main run method"""
        # Log current working directory for file location reference
        import os
        logger.info(f"Starting client. Files will be saved in: {os.getcwd()}")

        if not await self.connect():
            return

        await self.listen()

    async def close(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket connection closed")

async def main():
    """Main function"""
    client = OXDynamicWebSocketClient()

    try:
        await client.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    # Install required packages if not already installed:
    # pip install websockets

    # Run the client
    asyncio.run(main())
