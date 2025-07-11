import time
import threading
import database as db
import yfinance_client as yf_client
import notifier

def check_alerts():
    """The main loop for the alerter thread."""
    while True:
        print("Checking for alerts...")
        alerts = db.get_all_alerts()
        if not alerts:
            time.sleep(60) # Wait for a minute if there are no alerts
            continue

        for alert in alerts:
            try:
                process_alert(alert)
            except Exception as e:
                print(f"Error processing alert {alert[0]}: {e}")

        time.sleep(60) # Wait for a minute before the next check

def process_alert(alert):
    """Processes a single alert."""
    alert_id, stock_id, alert_type, threshold_percent, is_active, last_benchmark_price, current_state = alert

    if not is_active:
        return

    stock = db.get_stock_by_id(stock_id)
    if not stock:
        return

    ticker = stock[1]
    current_price = yf_client.get_current_prices([ticker]).get(ticker)

    if not current_price:
        return

    # Initialize state if it's the first time
    if not current_state:
        if alert_type == "Price Drops From Recent High":
            current_state = "watching_for_peak"
            last_benchmark_price = current_price
        else:
            current_state = "watching_for_trough"
            last_benchmark_price = current_price
        db.update_alert_state(alert_id, current_state, last_benchmark_price)

    # State machine logic
    if alert_type == "Price Drops From Recent High":
        if current_state == "watching_for_peak":
            if current_price > last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_peak", current_price)
            elif current_price < last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_drop", last_benchmark_price)
        elif current_state == "watching_for_drop":
            trigger_price = last_benchmark_price * (1 - threshold_percent / 100)
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
            if current_price >= trigger_price:
                send_notification(stock, alert_type, current_price, last_benchmark_price)
                db.update_alert_state(alert_id, "watching_for_trough", current_price)
            elif current_price < last_benchmark_price:
                db.update_alert_state(alert_id, "watching_for_trough", current_price)

def send_notification(stock, alert_type, current_price, benchmark_price):
    """Sends a notification for a triggered alert."""
    notification_service = db.get_setting("notification_service")
    api_key = db.get_setting("api_key")

    if not notification_service or not api_key or notification_service == "None":
        return

    title = f"Stock Alert: {stock[1]}"
    if alert_type == "Price Drops From Recent High":
        message = f"{stock[1]} has dropped to ${current_price:,.2f} from a recent high of ${benchmark_price:,.2f}."
    else:
        message = f"{stock[1]} has risen to ${current_price:,.2f} from a recent low of ${benchmark_price:,.2f}."

    if notification_service == "Pushover":
        # Note: Pushover requires two keys, but we are only storing one in the database.
        # This will need to be addressed in a future version.
        print("Sending Pushover notification...")
        # notifier.send_pushover_notification(api_key, "YOUR_APP_API_TOKEN", title, message)
    elif notification_service == "Pushbullet":
        print("Sending Pushbullet notification...")
        notifier.send_pushbullet_notification(api_key, title, message)

def start_alerter_thread():
    """Starts the alerter thread."""
    alerter_thread = threading.Thread(target=check_alerts, daemon=True)
    alerter_thread.start()
