import sqlite3
import os

def get_db_path():
    """Returns the absolute path to the database file in the user's AppData folder."""
    app_data_path = os.getenv('APPDATA')
    if not app_data_path:
        # Fallback for environments where APPDATA is not set
        app_data_path = os.path.expanduser('~')
    
    db_dir = os.path.join(app_data_path, 'StockAlert')
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, 'portfolio.db')

def get_connection():
    """Establishes and returns a database connection."""
    return sqlite3.connect(get_db_path())

def initialize_database():
    """
    Initializes the database and creates the necessary tables if they don't exist.
    Also handles migrating the schema if needed.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Create stocks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL UNIQUE,
            shares REAL,
            purchase_price REAL,
            currency TEXT
        )
    """)

    # --- Schema Migration ---
    # Add currency column to stocks table if it doesn't exist
    try:
        cursor.execute("SELECT currency FROM stocks LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating database: Adding 'currency' column to stocks table.")
        cursor.execute("ALTER TABLE stocks ADD COLUMN currency TEXT")

    # Add full_name column to stocks table if it doesn't exist
    try:
        cursor.execute("SELECT full_name FROM stocks LIMIT 1")
    except sqlite3.OperationalError:
        print("Migrating database: Adding 'full_name' column to stocks table.")
        cursor.execute("ALTER TABLE stocks ADD COLUMN full_name TEXT")


    # Create alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY,
            stock_id INTEGER,
            alert_type TEXT,
            threshold_percent REAL,
            is_active INTEGER,
            last_benchmark_price REAL,
            current_state TEXT,
            FOREIGN KEY (stock_id) REFERENCES stocks (id)
        )
    """)

    # Create settings table (key-value store)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()

    # Set default dashboard refresh interval if not already set
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("dashboard_refresh_interval", "300")) # Default to 5 minutes (300 seconds)
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ("minimize_to_tray", "True")) # Default to minimize to tray
    conn.commit()
    conn.close()

# --- Stock Functions ---

def add_stock(ticker, shares, purchase_price, currency):
    """Adds a new stock to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO stocks (ticker, shares, purchase_price, currency) VALUES (?, ?, ?, ?)",
                   (ticker.upper(), shares, purchase_price, currency))
    conn.commit()
    conn.close()

def update_stock_name(ticker, full_name):
    """Updates the full name of a stock."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE stocks SET full_name = ? WHERE ticker = ?", (full_name, ticker))
    conn.commit()
    conn.close()

def get_all_stocks():
    """Retrieves all stocks from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticker, full_name, shares, purchase_price, currency FROM stocks ORDER BY ticker")
    stocks = cursor.fetchall()
    conn.close()
    return stocks

def delete_stock(stock_id):
    """Deletes a stock and its associated alerts."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE stock_id = ?", (stock_id,))
    cursor.execute("DELETE FROM stocks WHERE id = ?", (stock_id,))
    conn.commit()
    conn.close()

# --- Alert Functions ---

def add_alert(stock_id, alert_type, threshold_percent):
    """Adds or replaces an alert for a stock."""
    conn = get_connection()
    cursor = conn.cursor()
    # Use INSERT OR REPLACE to ensure only one alert of a given type per stock
    cursor.execute("""
        INSERT OR REPLACE INTO alerts (id, stock_id, alert_type, threshold_percent, is_active, last_benchmark_price, current_state) 
        VALUES ((SELECT id FROM alerts WHERE stock_id = ? AND alert_type = ?), ?, ?, ?, 1, NULL, NULL)
    """, (stock_id, alert_type, stock_id, alert_type, threshold_percent))
    conn.commit()
    conn.close()

def get_stock_alerts(stock_id):
    """Retrieves all alerts for a specific stock."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, alert_type, threshold_percent, is_active FROM alerts WHERE stock_id = ?", (stock_id,))
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def update_alert_status(alert_id, is_active):
    """Updates the active status of an alert."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET is_active = ? WHERE id = ?", (1 if is_active else 0, alert_id))
    conn.commit()
    conn.close()

def delete_alert(alert_id):
    """Deletes an alert."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()

def get_stock_by_id(stock_id):
    """Retrieves a single stock by its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    # Select all columns explicitly to ensure order
    cursor.execute("SELECT id, ticker, full_name, shares, purchase_price, currency FROM stocks WHERE id = ?", (stock_id,))
    stock = cursor.fetchone()
    conn.close()
    return stock

def get_all_alerts():
    """Retrieves all active alerts from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE is_active = 1")
    alerts = cursor.fetchall()
    conn.close()
    return alerts

def update_alert_state(alert_id, current_state, last_benchmark_price):
    """Updates the state and benchmark price of an alert."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET current_state = ?, last_benchmark_price = ? WHERE id = ?", 
                   (current_state, last_benchmark_price, alert_id))
    conn.commit()
    conn.close()

# --- Settings Functions ---

def save_setting(key, value):
    """Saves a setting to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key):
    """Retrieves a setting from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

if __name__ == '__main__':
    initialize_database()
    print(f"Database initialized successfully at {get_db_path()}")
