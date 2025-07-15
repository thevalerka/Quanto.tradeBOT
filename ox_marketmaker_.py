import json
import time
import requests
import hashlib
import hmac
import base64
import logging
from datetime import datetime
import os
from typing import Dict, Optional, Any, List
from decimal import Decimal, ROUND_DOWN

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiCoinMarketMaker:
    def __init__(self, market_data_file="market_data_dynamic.json"):
        self.market_data_file = market_data_file
        self.last_market_data = None
        self.last_file_modified = 0

        # API credentials - MANIPULATOR account
        self.api_key = "XXXX"
        self.secret_key_str = "XXX"
        self.secret_key = self.secret_key_str.encode('utf-8')
        self.api_url = "api.ox.fun"

        # Trading state per coin
        self.positions = {}  # {market_code: {'position': float, 'entry_price': float}}
        self.active_orders = {}  # {market_code: {'buy': order_info, 'sell': order_info}}

        # Configuration
        self.config = {
            "min_spread_threshold": 0.007,  # 0.7% minimum spread to trade
            "min_distance_from_index": 0.004,  # 0.4% minimum distance from index price
            "order_value_usd": 5.5,  # $5.5 worth of each order
            "tick_size": 0.001,  # 1 tick = 0.1% (adjust per market if needed)
            "order_check_interval": 5,  # Check orders every 5 seconds
            "position_check_interval": 10,  # Check positions every 10 seconds
        }

    def _create_signature(self, method_type, endpoint, body=""):
        """Create API signature"""
        ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
        nonce = str(int(time.time() * 1000))
        msg_string = f"{ts}\n{nonce}\n{method_type}\n{self.api_url}\n{endpoint}\n{body}"
        sign = base64.b64encode(hmac.new(self.secret_key, msg_string.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

        return {
            'Content-Type': 'application/json',
            'AccessKey': self.api_key,
            'Timestamp': ts,
            'Signature': sign,
            'Nonce': nonce
        }

    def place_oxfun_order(self, market_code, side, quantity, price, time_in_force="GTC", order_type="LIMIT"):
        """Place order on OXFUN exchange"""
        method = "/v3/orders/place"
        client_order_id = int(time.time() * 1000)

        orders = [{
            "clientOrderId": client_order_id,
            "marketCode": market_code,
            "side": side,
            "quantity": str(quantity),
            "timeInForce": time_in_force,
            "orderType": order_type,
            "price": str(price)
        }]

        post_data = {
            "recvWindow": 20000,
            "responseType": "FULL",
            "timestamp": int(time.time() * 1000),
            "orders": orders
        }

        body = json.dumps(post_data)
        headers = self._create_signature("POST", method, body)

        try:
            response = requests.post(f"https://{self.api_url}{method}", data=body, headers=headers)
            response.raise_for_status()
            result = response.json()
            print(f"✅ Order placed: {side} {quantity} {market_code} @ {price}")
            return {
                'client_order_id': client_order_id,
                'market_code': market_code,
                'side': side,
                'quantity': quantity,
                'price': price,
                'time_in_force': time_in_force,
                'order_type': order_type,
                'response': result
            }
        except requests.exceptions.RequestException as error:
            print(f"❌ Error placing order: {error}")
            return None

    def get_working_orders(self, market_code=None):
        """Get working orders for specific market or all markets"""
        api_key = self.api_key
        secret_key = self.secret_key
        ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
        nonce = str(int(time.time() * 1000))
        method = "/v3/orders/working"
        api_url = "api.ox.fun"

        query_string = ""
        if market_code:
            query_string = f"marketCode={market_code}"

        msg_string = f"{ts}\n{nonce}\nGET\n{api_url}\n{method}\n{query_string}"
        sign = base64.b64encode(hmac.new(secret_key, msg_string.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

        headers = {
            'Content-Type': 'application/json',
            'AccessKey': api_key,
            'Timestamp': ts,
            'Signature': sign,
            'Nonce': nonce
        }

        url = f"https://{api_url}{method}"
        if query_string:
            url += f"?{query_string}"

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get('success'):
                return data.get('data', [])
            else:
                print(f'❌ Failed to fetch working orders: {data}')
                return []
        except requests.exceptions.RequestException as error:
            print(f'❌ Error fetching working orders: {error}')
            return []

    def cancel_all_orders(self, market_code):
        """Cancel all orders for specific market"""
        api_key = self.api_key
        secret_key = self.secret_key
        ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
        nonce = str(int(time.time() * 1000))
        method = "/v3/orders/cancel-all"
        api_url = "api.ox.fun"

        post_data = {
            "marketCode": market_code
        }

        body = json.dumps(post_data)
        msg_string = f"{ts}\n{nonce}\nDELETE\n{api_url}\n{method}\n{body}"
        sign = base64.b64encode(hmac.new(secret_key, msg_string.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

        headers = {
            'Content-Type': 'application/json',
            'AccessKey': api_key,
            'Timestamp': ts,
            'Signature': sign,
            'Nonce': nonce
        }

        try:
            response = requests.delete(f"https://{api_url}{method}", data=body, headers=headers)
            response.raise_for_status()
            result = response.json()
            print(f"🗑️ Cancelled all orders for {market_code}")
            return result
        except requests.exceptions.RequestException as error:
            print(f"❌ Error canceling orders for {market_code}: {error}")
            return None

    def get_positions(self, market_code):
        """Get position for specific market"""
        api_key = self.api_key
        secret_key = self.secret_key
        ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
        nonce = str(int(time.time() * 1000))
        method = "/v3/positions"
        api_url = "api.ox.fun"
        query_string = f"marketCode={market_code}"
        msg_string = f"{ts}\n{nonce}\nGET\n{api_url}\n{method}\n{query_string}"
        sign = base64.b64encode(hmac.new(secret_key, msg_string.encode('utf-8'), hashlib.sha256).digest()).decode('utf-8')

        headers = {
            'Content-Type': 'application/json',
            'AccessKey': api_key,
            'Timestamp': ts,
            'Signature': sign,
            'Nonce': nonce
        }

        try:
            response = requests.get(f"https://{api_url}{method}?{query_string}", headers=headers)
            response.raise_for_status()
            result = response.json()

            if result.get('success'):
                for account in result.get('data', []):
                    for position in account.get('positions', []):
                        if position['marketCode'] == market_code:
                            return position
                return None
            else:
                print(f"❌ Positions error for {market_code}: {result}")
                return None
        except requests.exceptions.RequestException as error:
            print(f"❌ Error getting positions for {market_code}: {error}")
            return None

    def load_market_data(self) -> Optional[Dict[str, Any]]:
        """Load market data from JSON file - handles both old and new format"""
        try:
            if not os.path.exists(self.market_data_file):
                return None

            file_modified = os.path.getmtime(self.market_data_file)
            if file_modified <= self.last_file_modified:
                return self.last_market_data

            with open(self.market_data_file, 'r') as f:
                raw_data = json.load(f)

            self.last_file_modified = file_modified

            # Handle new dynamic format with metadata
            if isinstance(raw_data, dict) and 'data' in raw_data:
                # New format: {"selected_coins": [...], "data": {market_code: coin_data, ...}}
                market_data = raw_data['data']
                selected_coins = raw_data.get('selected_coins', [])
                coins_with_positions = raw_data.get('coins_with_positions', [])

                logger.info(f"Loaded market data - Selected: {selected_coins}, With positions: {coins_with_positions}")
            elif isinstance(raw_data, dict):
                # Check if this looks like coin data (has typical coin data keys)
                first_key = next(iter(raw_data), None) if raw_data else None
                if first_key and isinstance(raw_data[first_key], dict) and 'bestAsk' in raw_data[first_key]:
                    # Old format: {market_code: coin_data, ...}
                    market_data = raw_data
                else:
                    logger.error("Unknown JSON format in market data file")
                    return None
            else:
                logger.error("Invalid JSON format in market data file")
                return None

            # Filter out any non-market-code entries and validate coin data
            filtered_data = {}
            for market_code, coin_data in market_data.items():
                if isinstance(coin_data, dict) and coin_data.get('last_updated'):
                    filtered_data[market_code] = coin_data

            self.last_market_data = filtered_data
            return filtered_data

        except Exception as e:
            logger.error(f"Error loading market data: {e}")
            return None

    def calculate_spread_percentage(self, coin_data: Dict[str, Any]) -> float:
        """Calculate bid-ask spread percentage"""
        if not coin_data.get('bestAsk') or not coin_data.get('bestBid'):
            return 0.0

        best_ask = float(coin_data['bestAsk'])
        best_bid = float(coin_data['bestBid'])
        mid_price = (best_ask + best_bid) / 2
        spread = best_ask - best_bid
        return spread / mid_price if mid_price > 0 else 0

    def calculate_distance_from_index(self, price: float, index_price: float) -> float:
        """Calculate distance from index price as percentage"""
        if index_price <= 0:
            return 0.0
        return abs(price - index_price) / index_price

    def check_multiple_orders_same_side(self, market_code: str) -> bool:
        """Check if there are multiple ask or bid orders for a coin"""
        working_orders = self.get_working_orders(market_code)

        if not working_orders:
            return False

        # Count orders by side
        buy_count = 0
        sell_count = 0

        for order in working_orders:
            if order.get('marketCode') == market_code:
                side = order.get('side', '').upper()
                if side == 'BUY':
                    buy_count += 1
                elif side == 'SELL':
                    sell_count += 1

        # Return True if more than 1 order on any side
        has_multiple = buy_count > 1 or sell_count > 1

        if has_multiple:
            print(f"   ⚠️ Multiple orders detected for {market_code}: {buy_count} BUY, {sell_count} SELL")

        return has_multiple

    def should_cancel_orders_due_to_narrow_spread(self, market_code: str, coin_data: Dict[str, Any]) -> bool:
        """Check if orders should be cancelled due to narrow spread (except when we have positions)"""
        # Don't cancel if we have a position - we need closing orders
        if self.has_position(market_code):
            return False

        # Check if spread is below threshold
        spread_pct = self.calculate_spread_percentage(coin_data)
        return spread_pct < self.config['min_spread_threshold']

    def should_make_market(self, coin_data: Dict[str, Any]) -> bool:
        """Check if we should make market for this coin"""
        # Check if we have all required data
        required_fields = ['bestAsk', 'bestBid', 'indexPrice']
        if not all(coin_data.get(field) for field in required_fields):
            return False

        # Check spread threshold
        spread_pct = self.calculate_spread_percentage(coin_data)
        if spread_pct < self.config['min_spread_threshold']:
            return False

        # Check distance from index price
        best_ask = float(coin_data['bestAsk'])
        best_bid = float(coin_data['bestBid'])
        index_price = float(coin_data['indexPrice'])

        ask_distance = self.calculate_distance_from_index(best_ask, index_price)
        bid_distance = self.calculate_distance_from_index(best_bid, index_price)

        # Only trade if either ask or bid is far enough from index
        return (ask_distance > self.config['min_distance_from_index'] or
                bid_distance > self.config['min_distance_from_index'])

    def calculate_order_quantity(self, price: float, market_code: str) -> float:
        """Calculate order quantity based on USD value"""
        if price <= 0:
            return 0.0

        # Calculate quantity for $5.5 worth
        quantity = self.config['order_value_usd'] / price

        # Round down to reasonable precision (adjust per market)
        # For most crypto, 3-4 decimal places should be fine
        return float(Decimal(str(quantity)).quantize(Decimal('0.001'), rounding=ROUND_DOWN))

    def calculate_market_making_prices(self, coin_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate bid and ask prices for market making"""
        best_ask = float(coin_data['bestAsk'])
        best_bid = float(coin_data['bestBid'])
        index_price = float(coin_data['indexPrice'])

        ask_distance = self.calculate_distance_from_index(best_ask, index_price)
        bid_distance = self.calculate_distance_from_index(best_bid, index_price)

        prices = {}

        # Place buy order 1 tick above BID if bid is far from index
        if bid_distance > self.config['min_distance_from_index']:
            tick_size = best_bid * self.config['tick_size']
            prices['buy_price'] = best_bid + tick_size

        # Place sell order 1 tick below ASK if ask is far from index
        if ask_distance > self.config['min_distance_from_index']:
            tick_size = best_ask * self.config['tick_size']
            prices['sell_price'] = best_ask - tick_size

        return prices

    def update_position_tracking(self, market_code: str):
        """Update position tracking from API"""
        position_data = self.get_positions(market_code)

        if position_data:
            position_size = float(position_data.get('position', 0))
            entry_price = float(position_data.get('entryPrice', 0)) if position_size != 0 else 0

            self.positions[market_code] = {
                'position': position_size,
                'entry_price': entry_price
            }
        else:
            self.positions[market_code] = {
                'position': 0.0,
                'entry_price': 0.0
            }

    def has_position(self, market_code: str) -> bool:
        """Check if we have a position in this market"""
        return market_code in self.positions and self.positions[market_code]['position'] != 0

    def place_closing_order(self, market_code: str, coin_data: Dict[str, Any]) -> bool:
        """Place order to close position"""
        if not self.has_position(market_code):
            return False

        position_size = self.positions[market_code]['position']
        best_ask = float(coin_data['bestAsk'])
        best_bid = float(coin_data['bestBid'])

        if position_size > 0:  # Long position - sell at best bid
            side = 'SELL'
            price = best_bid
        else:  # Short position - buy at best ask
            side = 'BUY'
            price = best_ask

        quantity = abs(position_size)

        result = self.place_oxfun_order(
            market_code=market_code,
            side=side,
            quantity=quantity,
            price=price,
            time_in_force="GTC"
        )

        if result:
            print(f"💰 Placed closing order for {market_code}: {side} {quantity} @ {price}")
            return True

        return False

    def place_market_making_orders(self, market_code: str, coin_data: Dict[str, Any]) -> bool:
        """Place market making orders for a coin"""
        # If we have a position, only place closing orders
        if self.has_position(market_code):
            return self.place_closing_order(market_code, coin_data)

        # Calculate market making prices
        prices = self.calculate_market_making_prices(coin_data)

        if not prices:
            return False

        success = True

        # Place buy order if price is calculated
        if 'buy_price' in prices:
            buy_quantity = self.calculate_order_quantity(prices['buy_price'], market_code)
            if buy_quantity > 0:
                buy_result = self.place_oxfun_order(
                    market_code=market_code,
                    side='BUY',
                    quantity=buy_quantity,
                    price=prices['buy_price']
                )
                if not buy_result:
                    success = False

        # Place sell order if price is calculated
        if 'sell_price' in prices:
            sell_quantity = self.calculate_order_quantity(prices['sell_price'], market_code)
            if sell_quantity > 0:
                sell_result = self.place_oxfun_order(
                    market_code=market_code,
                    side='SELL',
                    quantity=sell_quantity,
                    price=prices['sell_price']
                )
                if not sell_result:
                    success = False

        return success

    def manage_coin_orders(self, market_code: str, coin_data: Dict[str, Any]):
        """Manage orders for a specific coin"""
        print(f"\n🪙 Managing {market_code}")

        # Update position tracking
        self.update_position_tracking(market_code)

        # Check for multiple orders on same side - cancel all if detected
        if self.check_multiple_orders_same_side(market_code):
            print(f"   🗑️ Cancelling all orders - Multiple orders on same side detected")
            self.cancel_all_orders(market_code)
            return

        # Check if we should cancel orders due to narrow spread (but not if we have positions)
        if self.should_cancel_orders_due_to_narrow_spread(market_code, coin_data):
            spread_pct = self.calculate_spread_percentage(coin_data) * 100
            print(f"   🗑️ Cancelling orders - Spread too narrow: {spread_pct:.2f}% (need ≥{self.config['min_spread_threshold']*100:.1f}%)")
            self.cancel_all_orders(market_code)
            return

        # Check if we should make market
        if not self.should_make_market(coin_data):
            spread_pct = self.calculate_spread_percentage(coin_data) * 100
            print(f"   ⏭️ Skipping - Spread: {spread_pct:.2f}% (need ≥{self.config['min_spread_threshold']*100:.1f}%)")
            return

        # Cancel existing orders for this market before placing new ones
        self.cancel_all_orders(market_code)
        time.sleep(1)  # Wait for cancellation

        # Place new orders
        if self.place_market_making_orders(market_code, coin_data):
            print(f"   ✅ Orders placed for {market_code}")
        else:
            print(f"   ❌ Failed to place orders for {market_code}")

    def print_status(self, all_market_data: Dict[str, Any]):
        """Print current status for all coins"""
        print(f"\n📊 Market Maker Status - {datetime.now().strftime('%H:%M:%S')}")
        print(f"💰 Target order size: ${self.config['order_value_usd']}")
        print(f"📈 Min spread: {self.config['min_spread_threshold']*100:.1f}%")
        print(f"📏 Min distance from index: {self.config['min_distance_from_index']*100:.1f}%")
        print(f"🎯 Trading {len(all_market_data)} coins")

        for market_code, coin_data in all_market_data.items():
            if not coin_data.get('bestAsk') or not coin_data.get('bestBid'):
                continue

            spread_pct = self.calculate_spread_percentage(coin_data) * 100

            status_line = f"   {market_code}: Spread {spread_pct:.2f}%"

            if self.has_position(market_code):
                position_size = self.positions[market_code]['position']
                status_line += f" | Position: {position_size:+.3f}"

            # Check for multiple orders first
            if self.check_multiple_orders_same_side(market_code):
                status_line += " | 🗑️ Multiple orders (cancelling)"
            # Check market making eligibility
            elif self.should_make_market(coin_data):
                status_line += " | 🎯 Eligible"
            elif spread_pct < self.config['min_spread_threshold']*100:
                if self.has_position(market_code):
                    status_line += " | 💰 Position (closing only)"
                else:
                    status_line += " | 🗑️ Cancel orders"
            else:
                status_line += " | ⏭️ Skip"

            print(status_line)

    def cleanup_all_orders_at_startup(self, market_codes: List[str]):
        """Clean up any existing orders at startup"""
        print("🧹 Cleaning up existing orders at startup...")
        for market_code in market_codes:
            working_orders = self.get_working_orders(market_code)
            if working_orders:
                print(f"   Cancelling orders for {market_code}...")
                self.cancel_all_orders(market_code)
                time.sleep(1)
        print("✅ Startup cleanup completed")

    def run(self):
        """Main market making loop"""
        print("🏪 Multi-Coin Market Maker Bot Starting...")
        print(f"💰 Order size: ${self.config['order_value_usd']} per order")
        print(f"📈 Min spread threshold: {self.config['min_spread_threshold']*100:.1f}%")
        print(f"📏 Min distance from index: {self.config['min_distance_from_index']*100:.1f}%")
        print(f"🔄 Order check interval: {self.config['order_check_interval']}s")
        print(f"🗑️ Auto-cancel orders when spread < {self.config['min_spread_threshold']*100:.1f}% (except with positions)")
        print(f"📁 Reading market data from: {self.market_data_file}")

        last_order_check = 0
        last_status_time = 0

        try:
            while True:
                # Load market data
                all_market_data = self.load_market_data()
                if not all_market_data:
                    print("⏳ Waiting for market data...")
                    time.sleep(5)
                    continue

                current_time = time.time()
                market_codes = list(all_market_data.keys())

                # Cleanup at first run
                if last_order_check == 0:
                    self.cleanup_all_orders_at_startup(market_codes)

                # Print status every 30 seconds
                if current_time - last_status_time >= 30:
                    self.print_status(all_market_data)
                    last_status_time = current_time

                # Check and place orders every interval
                if current_time - last_order_check >= self.config['order_check_interval']:
                    for market_code in market_codes:
                        coin_data = all_market_data[market_code]
                        try:
                            self.manage_coin_orders(market_code, coin_data)
                            time.sleep(0.5)  # Brief pause between coins
                        except Exception as e:
                            print(f"❌ Error managing {market_code}: {e}")

                    last_order_check = current_time

                time.sleep(1)

        except KeyboardInterrupt:
            print(f"\n🛑 Stopping market maker...")
            print("🧹 Cleaning up all orders...")

            # Get final market data to clean up
            final_data = self.load_market_data()
            if final_data:
                for market_code in final_data.keys():
                    self.cancel_all_orders(market_code)
                    time.sleep(0.5)
        except Exception as e:
            logger.error(f"🚨 Error: {e}")
            print("🧹 Emergency cleanup...")

            # Emergency cleanup - try to cancel all orders
            final_data = self.load_market_data()
            if final_data:
                for market_code in final_data.keys():
                    try:
                        self.cancel_all_orders(market_code)
                    except:
                        pass

        print("💼 Market maker stopped")

def main():
    """Main function"""
    maker = MultiCoinMarketMaker()

    # You can adjust configuration here
    maker.config.update({
        "min_spread_threshold": 0.006,  # 0.6% minimum spread
        "min_distance_from_index": 0.004,  # 0.4% minimum distance from index
        "order_value_usd": 5.5,  # $5.5 per order
        "tick_size": 0.001,  # 0.1% tick size
        "order_check_interval": 5,  # Check every 5 seconds
    })

    maker.run()

if __name__ == "__main__":
    print("🏪 Multi-Coin Market Maker Bot")
    print("📋 Ensure WebSocket client is running and generating market_data_dynamic.json")
    print("⚠️  WARNING: This bot places real orders! Use at your own risk!")
    print("\n📊 Strategy:")
    print("   • Trade only coins in market_data_dynamic.json")
    print("   • Only trade if spread ≥ 0.6%")
    print("   • Cancel orders if spread < 0.6% (except when holding positions)")
    print("   • Cancel ALL orders if >1 ask or >1 bid order detected")
    print("   • Only trade if ask/bid > 0.4% from index price")
    print("   • Place orders 1 tick above bid and 1 tick below ask")
    print("   • $5.5 worth per order")
    print("   • If position exists, only place closing orders")
    print("\n🚀 Starting bot automatically...")

    main()
