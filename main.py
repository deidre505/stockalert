import customtkinter as ctk
import database as db
import yfinance_client as yf_client
import notifier as notifier
import alerter
import threading
import time
from tkinter import messagebox, ttk
from collections import defaultdict
import queue
import json
from PIL import Image
import pystray
from datetime import datetime

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
    is_running = False
    is_quitting = False
    def __init__(self):
        super().__init__()
        StockApp.is_running = True

        self.title("Stock Alert Dashboard")
        self.geometry("1200x800")

        db.initialize_database()

        self.tab_view = ctk.CTkTabview(self, anchor="nw")
        self.tab_view.pack(expand=True, fill="both", padx=10, pady=10)

        self.tab_view.add("Dashboard")
        self.tab_view.add("Add Stock")
        self.tab_view.add("Alerts")
        self.tab_view.add("Settings")

        self.summary_container = ctk.CTkFrame(self.tab_view.tab("Dashboard"))
        self.summary_container.pack(pady=10, padx=10, fill="x")
        self.summary_labels = {}
        self.currency_frames = {}

        self.setup_dashboard_tab()
        self.setup_add_stock_tab()
        self.setup_alerts_tab()
        self.setup_settings_tab()
        
        self._load_column_settings()
        
        self.refresh_dashboard()
        self.refresh_alerts_tab()

        alerter.start_alerter_thread()
        self.start_dashboard_refresh_thread()

        self.bind("<Control-Shift-D>", self.open_debug_window)
        self.check_ui_alert_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # System tray icon setup
        self.icon = None
        self.create_tray_icon()
        self.is_quitting = False
        self.is_quitting = False

    def create_tray_icon(self):
        image = Image.open("icon.png") # Ensure icon.png is in the same directory
        menu = (pystray.MenuItem('Show', self.show_window),
                pystray.MenuItem('Quit', self.quit_application))
        self.icon = pystray.Icon("Stock Alert", image, "Stock Alert", menu, on_double_click=self.show_window)
        self.icon.run_detached()

    def show_window(self, icon, item):
        if not self.is_quitting and self.winfo_exists():
            self.after(0, self.deiconify)
        else:
            # If the window is destroyed or quitting, stop the icon as it shouldn't be active
            icon.stop()

    def quit_application(self, icon, item):
        self.is_quitting = True # Signal that the app is quitting
        icon.stop()
        self.after(100, self.destroy) # Schedule destroy after a short delay

    def _on_closing(self):
        self._save_column_settings()
        
        # Get the current state of the minimize_to_tray switch directly
        should_minimize_to_tray = self.minimize_to_tray_switch.get()

        # Save this state to the database for future sessions
        db.save_setting("minimize_to_tray", str(should_minimize_to_tray))
        print(f"Minimize to tray setting: {should_minimize_to_tray}")

        if should_minimize_to_tray:
            self.withdraw() # Hide the window instead of destroying it
        else:
            self.is_quitting = True # Signal that the app is quitting
            # If not minimizing to tray, stop the pystray icon before destroying the main window
            if self.icon:
                self.icon.stop()
                self.icon = None # Clear the reference to the icon
            self.after(100, self.destroy) # Schedule destroy after a short delay

    def _save_column_settings(self):
        try:
            widths = {col: self.stock_tree.column(col, 'width') for col in self.stock_tree['columns']}
            db.save_setting('column_widths', json.dumps(widths))
            print("Column settings saved.")
        except Exception as e:
            print(f"Error saving column settings: {e}")

    def _load_column_settings(self):
        try:
            widths_json = db.get_setting('column_widths')
            if widths_json:
                widths = json.loads(widths_json)
                for col, width in widths.items():
                    if col in self.stock_tree['columns']:
                        self.stock_tree.column(col, width=width)
            print("Column settings loaded.")
        except Exception as e:
            print(f"Error loading column settings: {e}")

    def check_ui_alert_queue(self):
        try:
            alert_data = alerter.ui_alert_queue.get_nowait()
            messagebox.showinfo(alert_data["title"], alert_data["message"])
        except queue.Empty:
            pass
        finally:
            self.after(1000, self.check_ui_alert_queue)

    def open_debug_window(self, event=None):
        debug_window = ctk.CTkToplevel(self)
        debug_window.title("Debug Panel")
        debug_window.geometry("450x220")
        ctk.CTkLabel(debug_window, text="Inject Fake Price by Percentage", font=("Arial", 16)).pack(pady=10)
        stocks = db.get_all_stocks()
        stock_tickers = [s[1] for s in stocks]
        ctk.CTkLabel(debug_window, text="Stock Ticker:").pack()
        debug_ticker_optionmenu = ctk.CTkOptionMenu(debug_window, values=stock_tickers if stock_tickers else ["No stocks"])
        debug_ticker_optionmenu.pack(pady=5)
        ctk.CTkLabel(debug_window, text="Percentage Change (%):").pack()
        debug_percent_entry = ctk.CTkEntry(debug_window, placeholder_text="e.g., -10 for a 10% drop")
        debug_percent_entry.pack(pady=5)

        def inject():
            ticker = debug_ticker_optionmenu.get()
            percent_str = debug_percent_entry.get()
            if not ticker or not percent_str or ticker == "No stocks":
                messagebox.showerror("Error", "Please select a stock and enter a percentage.", parent=debug_window)
                return
            try:
                percent_change = float(percent_str)
                live_price_data = yf_client.get_current_prices([ticker])
                if not live_price_data or ticker not in live_price_data:
                    messagebox.showerror("Error", f"Could not fetch current price for {ticker}.", parent=debug_window)
                    return
                current_price = live_price_data[ticker]['price']
                fake_price = current_price * (1 + percent_change / 100)
                alerter.inject_fake_price(ticker, fake_price)
                messagebox.showinfo("Success", f"Fake price of {fake_price:,.2f} for {ticker} injected.", parent=debug_window)
                debug_window.destroy()
            except ValueError:
                messagebox.showerror("Error", "Percentage must be a number.", parent=debug_window)

        inject_button = ctk.CTkButton(debug_window, text="Enter", command=inject)
        inject_button.pack(pady=10)

    def setup_dashboard_tab(self):
        tab = self.tab_view.tab("Dashboard")
        
        columns = ("Name", "Ticker", "Shares", "Currency", "Purchase Price", "Current Price", "P/L", "P/L %")
        self.stock_tree = ttk.Treeview(tab, columns=columns, show='headings')
        
        for col in columns:
            self.stock_tree.heading(col, text=col.replace("_", " ").title())
            self.stock_tree.column(col, anchor='w')

        self.stock_tree.column("Name", width=200)
        self.stock_tree.column("Shares", width=80)
        self.stock_tree.column("Currency", width=80)
        self.stock_tree.column("Purchase Price", width=150)
        self.stock_tree.column("Current Price", width=150)
        self.stock_tree.column("P/L", width=150)
        self.stock_tree.column("P/L %", width=100)

        self.stock_tree.tag_configure('positive', foreground='green')
        self.stock_tree.tag_configure('negative', foreground='red')
        
        self.stock_tree.pack(expand=True, fill="both", padx=10, pady=10)

        button_frame = ctk.CTkFrame(tab)
        button_frame.pack(pady=10)
        refresh_button = ctk.CTkButton(button_frame, text="Refresh Data", command=self.refresh_dashboard)
        refresh_button.pack(side="left", padx=5)

        self.last_refreshed_label = ctk.CTkLabel(button_frame, text="")
        self.last_refreshed_label.pack(side="left", padx=5)

        delete_button = ctk.CTkButton(button_frame, text="Remove Selected Stock", command=self.delete_selected_stock)
        delete_button.pack(side="left", padx=5)

    def refresh_dashboard(self):
        for item in self.stock_tree.get_children():
            self.stock_tree.delete(item)

        stocks = db.get_all_stocks()
        if not stocks:
            for frame in self.currency_frames.values():
                frame.destroy()
            self.currency_frames.clear()
            self.summary_labels.clear()
            self.last_refreshed_label.configure(text="Last Refreshed: Never")
            return

        tickers_to_fetch = [s[1] for s in stocks if not s[2]]
        if tickers_to_fetch:
            live_data = yf_client.get_current_prices(tickers_to_fetch)
            for ticker, data in live_data.items():
                db.update_stock_name(ticker, data['full_name'])
            stocks = db.get_all_stocks()

        tickers = [s[1] for s in stocks]
        live_prices = yf_client.get_current_prices(tickers)

        portfolio_by_currency = defaultdict(lambda: {"stocks": [], "total_value": 0, "initial_cost": 0})
        for stock in stocks:
            portfolio_by_currency[stock[5]]["stocks"].append(stock)

        # Destroy frames for currencies that are no longer present
        for currency in list(self.currency_frames.keys()):
            if currency not in portfolio_by_currency:
                self.currency_frames[currency].destroy()
                del self.currency_frames[currency]
                del self.summary_labels[currency]

        for currency, data in portfolio_by_currency.items():
            symbol = get_currency_symbol(currency)
            
            if currency not in self.currency_frames:
                currency_frame = ctk.CTkFrame(self.summary_container)
                currency_frame.pack(pady=5, padx=5, fill="x")
                self.currency_frames[currency] = currency_frame
                
                ctk.CTkLabel(currency_frame, text=f"--- {currency} Portfolio ---", font=("Arial", 16, "bold")).pack(side="left", padx=10)
                
                value_label = ctk.CTkLabel(currency_frame, text="", font=("Arial", 14))
                value_label.pack(side="left", padx=10)
                
                pl_label = ctk.CTkLabel(currency_frame, text="", font=("Arial", 14))
                pl_label.pack(side="left", padx=10)
                
                self.summary_labels[currency] = {"value": value_label, "pl": pl_label}
            else:
                currency_frame = self.currency_frames[currency]

            total_value, initial_cost = 0, 0
            for stock in data["stocks"]:
                stock_id, ticker, full_name, shares, purchase_price, _ = stock
                current_price = live_prices.get(ticker, {}).get('price', 0)
                pl = (current_price - purchase_price) * shares if shares and shares > 0 else 0
                pl_percent = (pl / (purchase_price * shares) * 100) if shares and shares > 0 and purchase_price > 0 else 0
                tag = 'positive' if pl > 0 else ('negative' if pl < 0 else '')
                self.stock_tree.insert("", "end", values=(full_name, ticker, shares, currency, f"{symbol}{purchase_price:,.2f}", f"{symbol}{current_price:,.2f}", f"{symbol}{pl:,.2f}", f"{pl_percent:,.2f}%"), tags=(tag,))
                if shares and shares > 0:
                    total_value += current_price * shares
                    initial_cost += purchase_price * shares
            total_pl = total_value - initial_cost
            total_pl_percent = (total_pl / initial_cost * 100) if initial_cost > 0 else 0
            self.summary_labels[currency]["value"].configure(text=f"Total Value: {symbol}{total_value:,.2f}")
            self.summary_labels[currency]["pl"].configure(text=f"Total P/L: {symbol}{total_pl:,.2f} ({total_pl_percent:.2f}%)")

        self.last_refreshed_label.configure(text=f"Last Refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def delete_selected_stock(self):
        selected_item = self.stock_tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a stock to delete.")
            return
        ticker = self.stock_tree.item(selected_item, "values")[1]
        stock = self.get_stock_by_ticker(ticker)
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete this stock and all its associated alerts?"):
            try:
                db.delete_stock(stock[0])
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
        ticker, shares_str, price_str, currency = self.ticker_entry.get().upper(), self.shares_entry.get(), self.price_entry.get(), self.currency_optionmenu.get()
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
            for entry in [self.ticker_entry, self.shares_entry, self.price_entry]: entry.delete(0, 'end')
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
        for col in ("ID", "Stock", "Alert Type", "Threshold", "Status"): self.alerts_tree.heading(col, text=col)
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
        return next((s for s in db.get_all_stocks() if s[1] == ticker), None)

    def save_alert(self):
        stock_ticker, alert_type, threshold_str = self.alert_stock_optionmenu.get(), self.alert_type_optionmenu.get(), self.alert_threshold_entry.get()
        if not all([stock_ticker, alert_type, threshold_str]):
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
        for item in self.alerts_tree.get_children(): self.alerts_tree.delete(item)
        stocks = db.get_all_stocks()
        stock_tickers = [s[1] for s in stocks]
        self.alert_stock_optionmenu.configure(values=stock_tickers if stock_tickers else ["No stocks added"])
        if stock_tickers:
            self.alert_stock_optionmenu.set(stock_tickers[0])
        else:
            self.alert_stock_optionmenu.set("")
        for stock in stocks:
            for alert in db.get_stock_alerts(stock[0]):
                self.alerts_tree.insert("", "end", values=(alert[0], stock[1], alert[1], f"{alert[2]}%", "Active" if alert[3] else "Inactive"))

    def setup_settings_tab(self):
        tab = self.tab_view.tab("Settings")
        settings_frame = ctk.CTkFrame(tab)
        settings_frame.pack(padx=20, pady=20, fill="x")
        ctk.CTkLabel(settings_frame, text="Notification Service:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.notification_service_optionmenu = ctk.CTkOptionMenu(settings_frame, values=["None", "Pushover", "Pushbullet"], command=self.on_notification_service_change)
        self.notification_service_optionmenu.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        self.api_key_frame = ctk.CTkFrame(settings_frame)
        self.api_key_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        self.pushover_user_key_label = ctk.CTkLabel(self.api_key_frame, text="Pushover User Key:")
        self.pushover_user_key_entry = ctk.CTkEntry(self.api_key_frame, width=350)
        self.pushover_api_token_label = ctk.CTkLabel(self.api_key_frame, text="Pushover API Token:")
        self.pushover_api_token_entry = ctk.CTkEntry(self.api_key_frame, width=350)
        self.pushbullet_token_label = ctk.CTkLabel(self.api_key_frame, text="Pushbullet Access Token:")
        self.pushbullet_token_entry = ctk.CTkEntry(self.api_key_frame, width=350)
        ctk.CTkLabel(settings_frame, text="Dashboard Refresh Interval (seconds):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.refresh_interval_entry = ctk.CTkEntry(settings_frame, placeholder_text="e.g., 300")
        self.refresh_interval_entry.grid(row=2, column=1, padx=10, pady=10, sticky="w")

        ctk.CTkLabel(settings_frame, text="Minimize to System Tray on Close:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.minimize_to_tray_switch = ctk.CTkSwitch(settings_frame, text="")
        self.minimize_to_tray_switch.grid(row=3, column=1, padx=10, pady=10, sticky="w")
        
        settings_frame.grid_columnconfigure(1, weight=1)
        save_settings_button = ctk.CTkButton(tab, text="Save Settings", command=self.save_settings)
        save_settings_button.pack(padx=20, pady=20)
        self.load_settings()
        self.on_notification_service_change(self.notification_service_optionmenu.get())

    def on_notification_service_change(self, choice):
        for widget in self.api_key_frame.winfo_children(): widget.grid_remove()
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
        service, refresh_interval_str = self.notification_service_optionmenu.get(), self.refresh_interval_entry.get()
        try:
            refresh_interval = int(refresh_interval_str)
            if refresh_interval < 60: messagebox.showwarning("Warning", "A refresh interval below 60 seconds is not recommended.")
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
        if service: self.notification_service_optionmenu.set(service)
        pushover_user_key = db.get_setting("pushover_user_key")
        if pushover_user_key: self.pushover_user_key_entry.insert(0, pushover_user_key)
        pushover_api_token = db.get_setting("pushover_api_token")
        if pushover_api_token: self.pushover_api_token_entry.insert(0, pushover_api_token)
        pushbullet_token = db.get_setting("pushbullet_api_token")
        if pushbullet_token: self.pushbullet_token_entry.insert(0, pushbullet_token)
        refresh_interval = db.get_setting("dashboard_refresh_interval")
        if refresh_interval: self.refresh_interval_entry.insert(0, refresh_interval)

        minimize_to_tray = db.get_setting("minimize_to_tray")
        # Default to "True" if the setting is not found in the database
        if minimize_to_tray is None: 
            minimize_to_tray = "True"

        if minimize_to_tray == "True":
            self.minimize_to_tray_switch.select()
        else:
            self.minimize_to_tray_switch.deselect()

    def start_dashboard_refresh_thread(self):
        self.stop_event = threading.Event()
        interval = int(db.get_setting("dashboard_refresh_interval") or 300)
        self.dashboard_refresh_thread = threading.Thread(target=self._dashboard_refresh_loop, args=(interval, self.stop_event), daemon=True)
        self.dashboard_refresh_thread.start()

    def _dashboard_refresh_loop(self, interval, stop_event):
        while not stop_event.wait(interval):
            print("Refreshing dashboard data...")
            self.refresh_dashboard()

    def stop_dashboard_refresh_thread(self):
        if hasattr(self, 'stop_event'): self.stop_event.set()

if __name__ == "__main__":
    app = StockApp()
    app.mainloop()