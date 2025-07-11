import time
import threading
import database as db
import yfinance_client as yf_client
import notifier

# --- Currency Formatting ---

def get_currency_symbol(currency_code):
    """Returns the currency symbol for a given currency code."""
    symbols = {
        "USD": "$",
        "KRW": "₩",
        "JPY": "¥",
        "EUR": "€",
        "GBP": "£",
    }
    return symbols.get(currency_code, f"{currency_code} ")

# --- Alerter Logic ---

def check_alerts():
    """The main loop for the alerter thread."""
    while True:
        print("Checking for alerts...")
        alerts = db.get_all_alerts()
        if not alerts:
            time.sleep(60) # Wait for a minute if there are no alerts
            continue

        # Get all unique stock IDs from the alerts
        stock_ids = list(set(alert[1] for alert in alerts))
        
        # Fetch all required stock data in a batch
        stocks_by_id = {stock[0]: stock for stock in [db.get_stock_by_id(sid) for sid in stock_ids]}
        
        # Fetch all required price data in a batch
        tickers = [s[1] for s in stocks_by_id.values() if s]
        live_prices = yf_client.get_current_prices(tickers)

        for alert in alerts:
            try:
                stock = stocks_by_id.get(alert[1])
                if stock:
                    current_price = live_prices.get(stock[1])
                    if current_price:
                        process_alert(alert, stock, current_price)
            except Exception as e:
                print(f"Error processing alert {alert[0]}: {e}")

        time.sleep(60) # Wait for a minute before the next check

def process_alert(alert, stock, current_price):
    """Processes a single alert using pre-fetched data."""
    alert_id, stock_id, alert_type, threshold_percent, is_active, last_benchmark_price, current_state = alert

    if not is_active:
        return

    # Initialize state if it's the first time
    if not current_state:
        if alert_type == "Price Drops From Recent High":
            current_state = "watching_for_peak"
            last_benchmark_price = current_price
        else: # Price Rises From Recent Low
            current_state = "watching_for_trough"
            last_benchmark_price = current_price
        db.update_alert_state(alert_id, current_state, last_benchmark_price)
        return # Process on the next cycle

    # State machine logic
    if alert_type == "Price Drops From Recent High":
        if current_state == "watching_for_peak":
            if current_price > last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_peak", current_price)
            elif current_price < last_benchmark_price:
                # Price has started dropping, switch state
                db.update_alert_state(alert_id, "watching_for_drop", last_benchmark_price)
        elif current_state == "watching_for_drop":
            trigger_price = last_benchmark_price * (1 - threshold_percent / 100)
            if current_price <= trigger_price:
                send_notification(stock, alert_type, current_price, last_benchmark_price)
                # Reset after triggering
                db.update_alert_state(alert_id, "watching_for_peak", current_price)
            elif current_price > last_benchmark_price:
                # A new peak is forming, reset
                db.update_alert_state(alert_id, "watching_for_peak", current_price)

    elif alert_type == "Price Rises From Recent Low":
        if current_state == "watching_for_trough":
            if current_price < last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_trough", current_price)
            elif current_price > last_benchmark_price:
                # Price has started rising, switch state
                db.update_alert_state(alert_id, "watching_for_rise", last_benchmark_price)
        elif current_state == "watching_for_rise":
            trigger_price = last_benchmark_price * (1 + threshold_percent / 100)
            if current_price >= trigger_price:
                send_notification(stock, alert_type, current_price, last_benchmark_price)
                # Reset after triggering
                db.update_alert_state(alert_id, "watching_for_trough", current_price)
            elif current_price < last_benchmark_price:
                # A new trough is forming, reset
                db.update_alert_state(alert_id, "watching_for_trough", current_price)

def send_notification(stock, alert_type, current_price, benchmark_price):
    """Sends a notification for a triggered alert."""
    notification_service = db.get_setting("notification_service")

    if not notification_service or notification_service == "None":
        return

    stock_id, ticker, _, _, currency = stock
    symbol = get_currency_symbol(currency)

    title = f"Stock Alert: {ticker}"
    if alert_type == "Price Drops From Recent High":
        message = f"{ticker} has dropped to {symbol}{current_price:,.2f} from a recent high of {symbol}{benchmark_price:,.2f}."
    else: # Price Rises From Recent Low
        message = f"{ticker} has risen to {symbol}{current_price:,.2f} from a recent low of {symbol}{benchmark_price:,.2f}."

    if notification_service == "Pushover":
        user_key = db.get_setting("pushover_user_key")
        api_token = db.get_setting("pushover_api_token")
        if user_key and api_token:
            print(f"Sending Pushover notification: {title} - {message}")
            notifier.send_pushover_notification(user_key, api_token, title, message)
        else:
            print("Pushover notification failed: User Key or API Token not set.")

    elif notification_service == "Pushbullet":
        api_token = db.get_setting("pushbullet_api_token")
        if api_token:
            print(f"Sending Pushbullet notification: {title} - {message}")
            notifier.send_pushbullet_notification(api_token, title, message)
        else:
            print("Pushbullet notification failed: Access Token not set.")

def start_alerter_thread():
    """Starts the alerter thread."""
    alerter_thread = threading.Thread(target=check_alerts, daemon=True)
    alerter_thread.start()