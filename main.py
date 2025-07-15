import customtkinter as ctk
import database as db
import yfinance_client as yf_client
import notifier as notifier
import alerter
import threading
import time
from tkinter import messagebox, ttk
from collections import defaultdict

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

class StockApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Stock Alert Dashboard")
        self.geometry("1200x800")

        # Initialize database
        db.initialize_database()

        # Create the tab view
        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)

        # Add tabs
        self.tab_view.add("Dashboard")
        self.tab_view.add("Add Stock")
        self.tab_view.add("Alerts")
        self.tab_view.add("Settings")

        # Setup each tab
        self.setup_dashboard_tab()
        self.setup_add_stock_tab()
        self.setup_alerts_tab()
        self.setup_settings_tab()
        
        # Initial data load
        self.refresh_dashboard()
        self.refresh_alerts_tab()

        # Start the alerter thread
        alerter.start_alerter_thread()

        # Start the dashboard refresh thread
        self.start_dashboard_refresh_thread()

    def setup_dashboard_tab(self):
        tab = self.tab_view.tab("Dashboard")
        
        # --- Summary Frame ---
        self.summary_container = ctk.CTkFrame(tab)
        self.summary_container.pack(pady=10, padx=10, fill="x")
        self.summary_labels = {} # To hold labels for each currency

        # --- Treeview for stock list ---
        self.stock_tree = ttk.Treeview(tab, columns=("ID", "Ticker", "Shares", "Currency", "Purchase Price", "Current Price", "P/L", "P/L %"), show='headings')
        self.stock_tree.heading("ID", text="ID")
        self.stock_tree.heading("Ticker", text="Ticker")
        self.stock_tree.heading("Shares", text="Shares")
        self.stock_tree.heading("Currency", text="Currency")
        self.stock_tree.heading("Purchase Price", text="Avg. Purchase Price")
        self.stock_tree.heading("Current Price", text="Current Price")
        self.stock_tree.heading("P/L", text="Profit/Loss")
        self.stock_tree.heading("P/L %", text="P/L %")
        
        self.stock_tree.column("ID", width=40, anchor='center')
        self.stock_tree.column("Shares", width=80, anchor='e')
        self.stock_tree.column("Currency", width=80, anchor='center')
        self.stock_tree.column("Purchase Price", width=150, anchor='e')
        self.stock_tree.column("Current Price", width=150, anchor='e')
        self.stock_tree.column("P/L", width=150, anchor='e')
        self.stock_tree.column("P/L %", width=100, anchor='e')

        self.stock_tree.tag_configure('positive', foreground='green')
        self.stock_tree.tag_configure('negative', foreground='red')
        
        self.stock_tree.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Button Frame ---
        button_frame = ctk.CTkFrame(tab)
        button_frame.pack(pady=10)

        refresh_button = ctk.CTkButton(button_frame, text="Refresh Data", command=self.refresh_dashboard)
        refresh_button.pack(side="left", padx=5)

        delete_button = ctk.CTkButton(button_frame, text="Remove Selected Stock", command=self.delete_selected_stock)
        delete_button.pack(side="left", padx=5)

    def refresh_dashboard(self):
        # Clear existing data
        for item in self.stock_tree.get_children():
            self.stock_tree.delete(item)

        # Get stocks from DB
        stocks = db.get_all_stocks()
        if not stocks:
            for widget in self.summary_container.winfo_children():
                widget.destroy()
            return

        tickers = [s[1] for s in stocks]
        live_prices = yf_client.get_current_prices(tickers)

        portfolio_by_currency = defaultdict(lambda: {"stocks": [], "total_value": 0, "initial_cost": 0})
        for stock in stocks:
            stock_id, ticker, shares, purchase_price, currency = stock
            portfolio_by_currency[currency]["stocks"].append(stock)

        for widget in self.summary_container.winfo_children():
            widget.destroy()
        self.summary_labels.clear()

        for currency, data in portfolio_by_currency.items():
            symbol = get_currency_symbol(currency)
            
            currency_frame = ctk.CTkFrame(self.summary_container)
            currency_frame.pack(pady=5, padx=5, fill="x")
            
            ctk.CTkLabel(currency_frame, text=f"--- {currency} Portfolio ---", font=("Arial", 16, "bold")).pack(side="left", padx=10)
            
            value_label = ctk.CTkLabel(currency_frame, text="", font=("Arial", 14))
            value_label.pack(side="left", padx=10)
            
            pl_label = ctk.CTkLabel(currency_frame, text="", font=("Arial", 14))
            pl_label.pack(side="left", padx=10)
            
            self.summary_labels[currency] = {"value": value_label, "pl": pl_label}

        for currency, data in portfolio_by_currency.items():
            symbol = get_currency_symbol(currency)
            total_value = 0
            initial_cost = 0

            for stock in data["stocks"]:
                stock_id, ticker, shares, purchase_price, _ = stock
                current_price = live_prices.get(ticker, 0)
                
                pl = (current_price - purchase_price) * shares if shares and shares > 0 else 0
                pl_percent = (pl / (purchase_price * shares) * 100) if shares and shares > 0 and purchase_price > 0 else 0
                pl_text = f"{symbol}{pl:,.2f}"
                pl_percent_text = f"{pl_percent:,.2f}%"
                
                tag = ''
                if pl > 0:
                    tag = 'positive'
                elif pl < 0:
                    tag = 'negative'

                self.stock_tree.insert("", "end", values=(
                    stock_id, 
                    ticker, 
                    shares, 
                    currency,
                    f"{symbol}{purchase_price:,.2f}", 
                    f"{symbol}{current_price:,.2f}", 
                    pl_text,
                    pl_percent_text
                ), tags=(tag,))
                
                if shares and shares > 0:
                    total_value += current_price * shares
                    initial_cost += purchase_price * shares
            
            total_pl = total_value - initial_cost
            total_pl_percent = (total_pl / initial_cost * 100) if initial_cost > 0 else 0
            
            self.summary_labels[currency]["value"].configure(text=f"Total Value: {symbol}{total_value:,.2f}")
            self.summary_labels[currency]["pl"].configure(text=f"Total P/L: {symbol}{total_pl:,.2f} ({total_pl_percent:.2f}%)")


    def delete_selected_stock(self):
        selected_item = self.stock_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a stock to delete.")
            return

        stock_id = self.stock_tree.item(selected_item, "values")[0]

        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete this stock and all its associated alerts?"):
            try:
                db.delete_stock(stock_id)
                messagebox.showinfo("Success", "Stock and alerts deleted successfully.")
                self.refresh_dashboard()
                self.refresh_alerts_tab()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete stock: {e}")

    def setup_add_stock_tab(self):
        tab = self.tab_view.tab("Add Stock")
        
        form_frame = ctk.CTkFrame(tab)
        form_frame.pack(padx=20, pady=20, fill="x")

        ctk.CTkLabel(form_frame, text="Stock Ticker:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.ticker_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g., AAPL or 005930.KS")
        self.ticker_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(form_frame, text="Number of Shares:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.shares_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g., 100")
        self.shares_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(form_frame, text="Average Purchase Price:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.price_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g., 150.75")
        self.price_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(form_frame, text="Currency:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.currency_optionmenu = ctk.CTkOptionMenu(form_frame, values=["USD", "KRW", "JPY", "EUR", "GBP"])
        self.currency_optionmenu.grid(row=3, column=1, padx=10, pady=10, sticky="w")

        form_frame.grid_columnconfigure(1, weight=1)

        save_button = ctk.CTkButton(tab, text="Save Stock", command=self.save_stock)
        save_button.pack(padx=20, pady=10)

    def save_stock(self):
        ticker = self.ticker_entry.get().upper()
        shares_str = self.shares_entry.get()
        price_str = self.price_entry.get()
        currency = self.currency_optionmenu.get()

        if not ticker:
            messagebox.showerror("Error", "Stock Ticker is required.")
            return

        try:
            shares = float(shares_str) if shares_str else 0
            purchase_price = float(price_str) if price_str else 0
        except ValueError:
            messagebox.showerror("Error", "Shares and Purchase Price must be valid numbers.")
            return

        try:
            db.add_stock(ticker, shares, purchase_price, currency)
            messagebox.showinfo("Success", f"Stock {ticker} ({currency}) saved successfully.")
            self.ticker_entry.delete(0, 'end')
            self.shares_entry.delete(0, 'end')
            self.price_entry.delete(0, 'end')
            self.refresh_dashboard()
            self.refresh_alerts_tab()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save stock: {e}")


    def setup_alerts_tab(self):
        tab = self.tab_view.tab("Alerts")

        create_alert_frame = ctk.CTkFrame(tab)
        create_alert_frame.pack(pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(create_alert_frame, text="Create a New Alert", font=("Arial", 16)).pack(pady=5)

        ctk.CTkLabel(create_alert_frame, text="Stock:").pack(pady=(5,0))
        self.alert_stock_optionmenu = ctk.CTkOptionMenu(create_alert_frame, values=[])
        self.alert_stock_optionmenu.pack(pady=5)
        
        ctk.CTkLabel(create_alert_frame, text="Alert Type:").pack(pady=(5,0))
        self.alert_type_optionmenu = ctk.CTkOptionMenu(create_alert_frame, values=["Price Drops From Recent High", "Price Rises From Recent Low"])
        self.alert_type_optionmenu.pack(pady=5)

        ctk.CTkLabel(create_alert_frame, text="Threshold (%):").pack(pady=(5,0))
        self.alert_threshold_entry = ctk.CTkEntry(create_alert_frame, placeholder_text="e.g., 5")
        self.alert_threshold_entry.pack(pady=5)

        save_alert_button = ctk.CTkButton(create_alert_frame, text="Save Alert", command=self.save_alert)
        save_alert_button.pack(pady=10)

        existing_alerts_frame = ctk.CTkFrame(tab)
        existing_alerts_frame.pack(pady=10, padx=10, fill="both", expand=True)

        ctk.CTkLabel(existing_alerts_frame, text="Your Alerts", font=("Arial", 16)).pack(pady=5)

        self.alerts_tree = ttk.Treeview(existing_alerts_frame, columns=("ID", "Stock", "Alert Type", "Threshold", "Status"), show='headings')
        self.alerts_tree.heading("ID", text="ID")
        self.alerts_tree.heading("Stock", text="Stock")
        self.alerts_tree.heading("Alert Type", text="Alert Type")
        self.alerts_tree.heading("Threshold", text="Threshold (%)")
        self.alerts_tree.heading("Status", text="Status")
        self.alerts_tree.column("ID", width=40)
        self.alerts_tree.pack(expand=True, fill="both", padx=10, pady=10)

        delete_alert_button = ctk.CTkButton(existing_alerts_frame, text="Delete Selected Alert", command=self.delete_selected_alert)
        delete_alert_button.pack(pady=10)
        
        self.refresh_alerts_tab()

    def delete_selected_alert(self):
        selected_item = self.alerts_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select an alert to delete.")
            return

        alert_id = self.alerts_tree.item(selected_item, "values")[0]

        try:
            db.delete_alert(alert_id)
            messagebox.showinfo("Success", "Alert deleted successfully.")
            self.refresh_alerts_tab()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete alert: {e}")

    def get_stock_by_ticker(self, ticker):
        stocks = db.get_all_stocks()
        for stock in stocks:
            if stock[1] == ticker:
                return stock
        return None

    def save_alert(self):
        stock_ticker = self.alert_stock_optionmenu.get()
        alert_type = self.alert_type_optionmenu.get()
        threshold_str = self.alert_threshold_entry.get()

        if not stock_ticker or not alert_type or not threshold_str:
            messagebox.showerror("Error", "Please fill in all fields.")
            return

        try:
            threshold = float(threshold_str)
        except ValueError:
            messagebox.showerror("Error", "Threshold must be a valid number.")
            return

        stock = self.get_stock_by_ticker(stock_ticker)
        if not stock:
            messagebox.showerror("Error", f"Could not find stock with ticker {stock_ticker}.")
            return

        try:
            db.add_alert(stock[0], alert_type, threshold)
            messagebox.showinfo("Success", f"Alert for {stock_ticker} saved successfully.")
            self.refresh_alerts_tab()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save alert: {e}")

    def refresh_alerts_tab(self):
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)

        stocks = db.get_all_stocks()
        stock_tickers = [s[1] for s in stocks]
        self.alert_stock_optionmenu.configure(values=stock_tickers if stock_tickers else ["No stocks added"])
        if stock_tickers:
            self.alert_stock_optionmenu.set(stock_tickers[0])
        else:
            self.alert_stock_optionmenu.set("")

        for stock in stocks:
            alerts = db.get_stock_alerts(stock[0])
            for alert in alerts:
                alert_id, alert_type, threshold_percent, is_active = alert
                status = "Active" if is_active else "Inactive"
                self.alerts_tree.insert("", "end", values=(alert_id, stock[1], alert_type, f"{threshold_percent}%", status))

    def setup_settings_tab(self):
        tab = self.tab_view.tab("Settings")

        # --- Main Settings Frame ---
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=20, fill="x")

        # --- Notification Service ---
        ctk.CTkLabel(settings_frame, text="Notification Service:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.notification_service_optionmenu = ctk.CTkOptionMenu(
            settings_frame,
            values=["None", "Pushover", "Pushbullet"],
            command=self.on_notification_service_change
        )
        self.notification_service_optionmenu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        # --- Dynamic API Key Frame ---
        self.api_key_frame = ctk.CTkFrame(settings_frame)
        self.api_key_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # --- Pushover Fields ---
        self.pushover_user_key_label = ctk.CTkLabel(self.api_key_frame, text="Pushover User Key:")
        self.pushover_user_key_entry = ctk.CTkEntry(self.api_key_frame, width=350)
        self.pushover_api_token_label = ctk.CTkLabel(self.api_key_frame, text="Pushover API Token:")
        self.pushover_api_token_entry = ctk.CTkEntry(self.api_key_frame, width=350)

        # --- Pushbullet Fields ---
        self.pushbullet_token_label = ctk.CTkLabel(self.api_key_frame, text="Pushbullet Access Token:")
        self.pushbullet_token_entry = ctk.CTkEntry(self.api_key_frame, width=350)

        # --- Dashboard Refresh Interval ---
        ctk.CTkLabel(settings_frame, text="Dashboard Refresh Interval (seconds):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.refresh_interval_entry = ctk.CTkEntry(settings_frame, placeholder_text="e.g., 300")
        self.refresh_interval_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")
        
        settings_frame.grid_columnconfigure(1, weight=1)

        # --- Save Button ---
        save_settings_button = ctk.CTkButton(tab, text="Save Settings", command=self.save_settings)
        save_settings_button.pack(padx=20, pady=20)

        self.load_settings()
        self.on_notification_service_change(self.notification_service_optionmenu.get())

    def on_notification_service_change(self, choice):
        for widget in self.api_key_frame.winfo_children():
            widget.grid_remove()

        if choice == "Pushover":
            self.pushover_user_key_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
            self.pushover_user_key_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
            self.pushover_api_token_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
            self.pushover_api_token_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        elif choice == "Pushbullet":
            self.pushbullet_token_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
            self.pushbullet_token_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        self.api_key_frame.grid_columnconfigure(1, weight=1)

    def save_settings(self):
        service = self.notification_service_optionmenu.get()
        refresh_interval_str = self.refresh_interval_entry.get()

        try:
            refresh_interval = int(refresh_interval_str)
            if refresh_interval < 60:
                messagebox.showwarning("Warning", "A refresh interval below 60 seconds is not recommended.")
        except ValueError:
            messagebox.showerror("Error", "Refresh interval must be a valid positive integer.")
            return

        try:
            db.save_setting("notification_service", service)
            db.save_setting("dashboard_refresh_interval", str(refresh_interval))

            if service == "Pushover":
                db.save_setting("pushover_user_key", self.pushover_user_key_entry.get())
                db.save_setting("pushover_api_token", self.pushover_api_token_entry.get())
            elif service == "Pushbullet":
                db.save_setting("pushbullet_api_token", self.pushbullet_token_entry.get())

            messagebox.showinfo("Success", "Settings saved successfully.")
            self.stop_dashboard_refresh_thread()
            self.start_dashboard_refresh_thread()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_settings(self):
        service = db.get_setting("notification_service")
        if service:
            self.notification_service_optionmenu.set(service)

        pushover_user_key = db.get_setting("pushover_user_key")
        if pushover_user_key:
            self.pushover_user_key_entry.insert(0, pushover_user_key)
            
        pushover_api_token = db.get_setting("pushover_api_token")
        if pushover_api_token:
            self.pushover_api_token_entry.insert(0, pushover_api_token)

        pushbullet_token = db.get_setting("pushbullet_api_token")
        if pushbullet_token:
            self.pushbullet_token_entry.insert(0, pushbullet_token)

        refresh_interval = db.get_setting("dashboard_refresh_interval")
        if refresh_interval:
            self.refresh_interval_entry.delete(0, ctk.END)
            self.refresh_interval_entry.insert(0, refresh_interval)

    def start_dashboard_refresh_thread(self):
        self.stop_event = threading.Event()
        interval_str = db.get_setting("dashboard_refresh_interval")
        interval = int(interval_str) if interval_str else 300
        
        self.dashboard_refresh_thread = threading.Thread(target=self._dashboard_refresh_loop, args=(interval, self.stop_event), daemon=True)
        self.dashboard_refresh_thread.start()

    def _dashboard_refresh_loop(self, interval, stop_event):
        while not stop_event.wait(interval):
            print("Refreshing dashboard data...")
            self.refresh_dashboard()

    def stop_dashboard_refresh_thread(self):
        if hasattr(self, 'stop_event'):
            self.stop_event.set()

if __name__ == "__main__":
    app = StockApp()
    app.mainloop()