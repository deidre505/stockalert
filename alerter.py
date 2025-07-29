import time
import threading
import database as db
import yfinance_client as yf_client
import notifier
import queue

# Queue for sending alerts to the UI thread
ui_alert_queue = queue.Queue()

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

debug_fake_price = None
alerter_thread_instance = None

def inject_fake_price(ticker, price):
    """Injects a fake price for a specific ticker for one check cycle."""
    global debug_fake_price
    print(f"[DEBUG] Injecting fake price for {ticker}: {price}")
    debug_fake_price = {"ticker": ticker, "price": price}

def check_alerts():
    """The main loop for the alerter thread."""
    global debug_fake_price
    while True:
        # --- Debug Price Injection Check ---
        if debug_fake_price:
            # If a fake price is present, process it immediately
            # This ensures the test happens right away, not after the next sleep cycle
            print("[DEBUG] Prioritizing fake price check.")
            fake_ticker = debug_fake_price.get("ticker")
            fake_price = debug_fake_price.get("price")
            alerts = db.get_all_alerts()
            stock_to_check = None
            alert_to_check = None

            # Find the specific stock and alert for the fake ticker
            for alert in alerts:
                stock = db.get_stock_by_id(alert[1])
                if stock and stock[1] == fake_ticker:
                    stock_to_check = stock
                    alert_to_check = alert
                    break
            
            if stock_to_check and alert_to_check:
                print(f"[DEBUG] Processing injected price {fake_price} for {fake_ticker}.")
                process_alert(alert_to_check, stock_to_check, fake_price)
            else:
                print(f"[DEBUG] Could not find an active alert for ticker {fake_ticker}.")

            debug_fake_price = None # Reset after use
            # Continue to the regular check after handling the fake price

        print("Checking for alerts...")
        alerts = db.get_all_alerts()
        if not alerts:
            time.sleep(60) # Wait for a minute if there are no alerts
            continue

        stock_ids = list(set(alert[1] for alert in alerts))
        stocks_by_id = {stock[0]: stock for stock in [db.get_stock_by_id(sid) for sid in stock_ids]}
        tickers = [s[1] for s in stocks_by_id.values() if s]
        live_prices = yf_client.get_current_prices(tickers)

        for alert in alerts:
            try:
                stock = stocks_by_id.get(alert[1])
                if stock:
                    current_price_data = live_prices.get(stock[1])
                    if current_price_data:
                        current_price = current_price_data['price']
                        process_alert(alert, stock, current_price)
            except Exception as e:
                print(f"Error processing alert {alert[0]}: {e}")

        time.sleep(60) # Wait for a minute before the next check

def process_alert(alert, stock, current_price):
    """Processes a single alert using pre-fetched data."""
    alert_id, stock_id, alert_type, threshold_percent, target_price, is_active, last_benchmark_price, current_state = alert

    if not is_active:
        return

    if alert_type == "Price Rises Above":
        if target_price is not None and current_price >= target_price:
            send_notification(stock, alert_type, current_price, target_price)
            db.update_alert_status(alert_id, False)
        return
    elif alert_type == "Price Falls Below":
        if target_price is not None and current_price <= target_price:
            send_notification(stock, alert_type, current_price, target_price)
            db.update_alert_status(alert_id, False)
        return

    if not current_state:
        if alert_type == "Price Drops From Recent High":
            current_state = "watching_for_peak"
            last_benchmark_price = current_price
        else: # Price Rises From Recent Low
            current_state = "watching_for_trough"
            last_benchmark_price = current_price
        db.update_alert_state(alert_id, current_state, last_benchmark_price)
        print(f"[STATE] Initialized alert {alert_id} for {stock[1]} to state: {current_state} with benchmark: {last_benchmark_price}")
        return

    print(f"[PROCESS] Alert:{alert_id}, Stock:{stock[1]}, Type:{alert_type}, State:{current_state}, CurrentPrice:{current_price}, Benchmark:{last_benchmark_price}")

    if alert_type == "Price Drops From Recent High":
        if current_state == "watching_for_peak":
            if current_price > last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_peak", current_price)
            elif current_price < last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_drop", last_benchmark_price)
        elif current_state == "watching_for_drop":
            trigger_price = last_benchmark_price * (1 - threshold_percent / 100)
            print(f"[EVAL] {stock[1]}: Current {current_price} <= Trigger {trigger_price:.2f}?")
            if current_price <= trigger_price:
                send_notification(stock, alert_type, current_price, last_benchmark_price)
                db.update_alert_state(alert_id, "watching_for_peak", current_price)
            elif current_price > last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_peak", current_price)

    elif alert_type == "Price Rises From Recent Low":
        if current_state == "watching_for_trough":
            if current_price < last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_trough", current_price)
            elif current_price > last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_rise", last_benchmark_price)
        elif current_state == "watching_for_rise":
            trigger_price = last_benchmark_price * (1 + threshold_percent / 100)
            print(f"[EVAL] {stock[1]}: Current {current_price} >= Trigger {trigger_price:.2f}?")
            if current_price >= trigger_price:
                send_notification(stock, alert_type, current_price, last_benchmark_price)
                db.update_alert_state(alert_id, "watching_for_trough", current_price)
            elif current_price < last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_trough", current_price)

def send_notification(stock, alert_type, current_price, benchmark_price):
    """Sends a notification for a triggered alert."""
    stock_id, ticker, full_name, _, _, currency = stock
    symbol = get_currency_symbol(currency)

    title = f"Stock Alert: {ticker}"
    if alert_type == "Price Drops From Recent High":
        message = f"{full_name} ({ticker}) has dropped to {symbol}{current_price:,.2f} from a recent high of {symbol}{benchmark_price:,.2f}."
    elif alert_type == "Price Rises From Recent Low":
        message = f"{full_name} ({ticker}) has risen to {symbol}{current_price:,.2f} from a recent low of {symbol}{benchmark_price:,.2f}."
    elif alert_type == "Price Rises Above":
        message = f"{full_name} ({ticker}) has risen above your target of {symbol}{benchmark_price:,.2f} and is currently at {symbol}{current_price:,.2f}."
    elif alert_type == "Price Falls Below":
        message = f"{full_name} ({ticker}) has fallen below your target of {symbol}{benchmark_price:,.2f} and is currently at {symbol}{current_price:,.2f}."

    print(f"[NOTIFICATION] Triggered for {ticker}. Sending alert.")
    ui_alert_queue.put({"title": title, "message": message})

    notification_service = db.get_setting("notification_service")
    if not notification_service or notification_service == "None":
        print("[NOTIFICATION] No mobile service configured.")
        return

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
    global alerter_thread_instance
    if alerter_thread_instance is None:
        alerter_thread_instance = threading.Thread(target=check_alerts, daemon=True)
        alerter_thread_instance.start()
