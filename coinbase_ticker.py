import websocket
import json
import threading
import time
from statistics import mean
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Specify the product ID you want to monitor (e.g., "BTC-USD", "ETH-USD", etc.)
product_id = input("Specify the product ID you want to monitor (e.g., BTC-USD, ETH-USD, etc.) (empty string would be defaulted to BTC-USD): ")
if product_id == '':
    product_id = 'BTC-USD'

entries_per_minute = 12

# Metrics and data storage
metrics = {
    "highest_bid": 0,
    "lowest_ask": float('inf'),
    "highest_bid_quantity": 0,
    "lowest_ask_quantity": 0,
    "max_bid_ask_difference": [],
    "mid_prices": [],
    "forecasted_mid_prices": [],
    "forecasting_errors": [],
}



def process_ticker(ticker_data):
    best_bid = float(ticker_data["best_bid"])
    best_ask = float(ticker_data["best_ask"])    
    best_bid_quantity = float(ticker_data["best_bid_size"]) if "best_bid_size" in ticker_data else 0
    best_ask_quantity = float(ticker_data["best_ask_size"]) if "best_ask_size" in ticker_data else 0
    
    metrics["highest_bid"] = best_bid
    metrics["lowest_ask"] = best_ask
    metrics["highest_bid_quantity"] = best_bid_quantity
    metrics["lowest_ask_quantity"] = best_ask_quantity
        


def calculate_metrics():
    mid_price = (metrics["highest_bid"] + metrics["lowest_ask"]) / 2
    diff = metrics["lowest_ask"] - metrics["highest_bid"]
    metrics["mid_prices"].append(mid_price)
    metrics["max_bid_ask_difference"].append(diff)
    print(f"{len(metrics['mid_prices'])}")
    
    avg_mid_price_1min = mean(metrics["mid_prices"][-entries_per_minute:])
    avg_mid_price_5min = mean(metrics["mid_prices"][-(entries_per_minute*5):])
    avg_mid_price_15min = mean(metrics["mid_prices"][-(entries_per_minute*15):])
    
    forecasted_mid_price_1min = calculate_forecast_exp_smooth(entries_per_minute)
    
    if forecasted_mid_price_1min is not None:
        metrics["forecasted_mid_prices"].append(forecasted_mid_price_1min)
    
    if len(metrics["forecasted_mid_prices"]) > (entries_per_minute*15):
        metrics["forecasted_mid_prices"].pop(0)
    
    avg_forecasting_error_1min = calculate_forecasting_error(1)
    avg_forecasting_error_5min = calculate_forecasting_error(5)
    avg_forecasting_error_15min = calculate_forecasting_error(15) 
   
    print(f"Current Highest Bid: {metrics['highest_bid']} (Quantity: {metrics['highest_bid_quantity']})")
    print(f"Current Lowest Ask: {metrics['lowest_ask']} (Quantity: {metrics['lowest_ask_quantity']})")
    print(f"Max Bid-Ask Difference: {max(metrics['max_bid_ask_difference'])}")
    print(f"Average Mid-Price (1 min): {avg_mid_price_1min}")
    print(f"Average Mid-Price (5 min): {avg_mid_price_5min}")
    print(f"Average Mid-Price (15 min): {avg_mid_price_15min}")
    print(f"Forecasted Mid-Price (60 sec): {metrics['forecasted_mid_prices'][-1] if metrics['forecasted_mid_prices'] else 'N/A'}")
    print(f"Average Forecasting Error (1 min): {avg_forecasting_error_1min}")
    print(f"Average Forecasting Error (5 min): {avg_forecasting_error_5min}")
    print(f"Average Forecasting Error (15 min): {avg_forecasting_error_15min}")
    print("=" * 30)


def calculate_forecast_exp_smooth(window_size_entries):
    if len(metrics["mid_prices"]) < (window_size_entries*2):
        return None

    model = ExponentialSmoothing(metrics["mid_prices"], trend='add', seasonal='add', damped_trend=True, seasonal_periods=entries_per_minute, initialization_method='estimated')
    model_fit = model.fit()
    forecast = model_fit.forecast(window_size_entries)
    return forecast[-1]


def calculate_forecasting_error(window_size_minutes):
    if len(metrics["forecasted_mid_prices"]) < window_size_minutes or len(metrics["mid_prices"]) < (entries_per_minute*3):
        return None
    
    forecasted_mid_prices_window = metrics["forecasted_mid_prices"][-(window_size_minutes*entries_per_minute):]
    actual_mid_prices_window = metrics["mid_prices"][-(window_size_minutes*entries_per_minute):]
    if len(forecasted_mid_prices_window) < len(actual_mid_prices_window):
        return None
    
    forecasting_errors = [abs(forecasted - actual) for forecasted, actual in zip(forecasted_mid_prices_window, actual_mid_prices_window)]
    avg_forecasting_error = mean(forecasting_errors)    
    return avg_forecasting_error



def on_message(ws, message):
    data = json.loads(message)    
    if "type" in data:
        if data["type"] == "ticker" and "best_bid" in data and "best_ask" in data:
            process_ticker(data)

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Connection closed")

def on_open(ws):
    def run():
        subscribe_message = {
            "type": "subscribe",
            "product_ids": [product_id],
            "channels": ["ticker"]
        }
        ws.send(json.dumps(subscribe_message))
    
    threading.Thread(target=run).start()

if __name__ == "__main__":
    # websocket.enableTrace(True)
    
    ws_url = "wss://ws-feed.exchange.coinbase.com"
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    
    ws_thread = threading.Thread(target=ws.run_forever)
    ws_thread.start()
    
    try:
        while True:
            time.sleep(5)
            calculate_metrics()
    except KeyboardInterrupt:
        ws.close()
