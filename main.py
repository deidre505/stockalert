import customtkinter as ctk
import database as db
import yfinance_client as yf_client
import notifier as notifier
import alerter
import threading
import time
from tkinter import messagebox, ttk

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
        self.tab_view.add("Add/Edit Stock")
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
        
        # Summary Frame
        summary_frame = ctk.CTkFrame(tab)
        summary_frame.pack(pady=10, padx=10, fill="x")
        
        self.total_value_label = ctk.CTkLabel(summary_frame, text="Total Portfolio Value: $0.00", font=("Arial", 16))
        self.total_value_label.pack(side="left", padx=20)
        
        self.total_pl_label = ctk.CTkLabel(summary_frame, text="Total P/L: $0.00 (0.00%)", font=("Arial", 16))
        self.total_pl_label.pack(side="left", padx=20)

        # Treeview for stock list
        self.stock_tree = ttk.Treeview(tab, columns=("ID", "Ticker", "Shares", "Purchase Price", "Current Price", "P/L"), show='headings')
        self.stock_tree.heading("ID", text="ID")
        self.stock_tree.heading("Ticker", text="Ticker")
        self.stock_tree.heading("Shares", text="Shares")
        self.stock_tree.heading("Purchase Price", text="Avg. Purchase Price")
        self.stock_tree.heading("Current Price", text="Current Price")
        self.stock_tree.heading("P/L", text="Profit/Loss")
        self.stock_tree.column("ID", width=40)
        self.stock_tree.pack(expand=True, fill="both", padx=10, pady=10)

        # Button Frame
        button_frame = ctk.CTkFrame(tab)
        button_frame.pack(pady=10)

        # Refresh Button
        refresh_button = ctk.CTkButton(button_frame, text="Refresh Data", command=self.refresh_dashboard)
        refresh_button.pack(side="left", padx=5)

        # Delete Button
        delete_button = ctk.CTkButton(button_frame, text="Remove Selected Stock", command=self.delete_selected_stock)
        delete_button.pack(side="left", padx=5)

    def refresh_dashboard(self):
        # Clear existing data
        for item in self.stock_tree.get_children():
            self.stock_tree.delete(item)

        # Get stocks from DB
        stocks = db.get_all_stocks()
        if not stocks:
            return

        tickers = [s[1] for s in stocks]
        live_prices = yf_client.get_current_prices(tickers)

        total_portfolio_value = 0
        total_initial_cost = 0

        for stock in stocks:
            stock_id, ticker, shares, purchase_price = stock
            current_price = live_prices.get(ticker, 0)
            
            pl = (current_price - purchase_price) * shares if shares > 0 else 0
            pl_text = f"${pl:,.2f}"
            
            self.stock_tree.insert("", "end", values=(stock_id, ticker, shares, f"${purchase_price:,.2f}", f"${current_price:,.2f}", pl_text))
            
            total_portfolio_value += current_price * shares
            total_initial_cost += purchase_price * shares

        total_pl = total_portfolio_value - total_initial_cost
        total_pl_percent = (total_pl / total_initial_cost * 100) if total_initial_cost > 0 else 0
        
        self.total_value_label.configure(text=f"Total Portfolio Value: ${total_portfolio_value:,.2f}")
        self.total_pl_label.configure(text=f"Total P/L: ${total_pl:,.2f} ({total_pl_percent:.2f}%)")

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
        tab = self.tab_view.tab("Add/Edit Stock")
        
        # Create a frame for the form
        form_frame = ctk.CTkFrame(tab)
        form_frame.pack(padx=20, pady=20, fill="x")

        # Ticker
        ctk.CTkLabel(form_frame, text="Stock Ticker:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.ticker_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g., AAPL")
        self.ticker_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Shares
        ctk.CTkLabel(form_frame, text="Number of Shares:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.shares_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g., 100")
        self.shares_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Purchase Price
        ctk.CTkLabel(form_frame, text="Average Purchase Price:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.price_entry = ctk.CTkEntry(form_frame, placeholder_text="e.g., 150.75")
        self.price_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        form_frame.grid_columnconfigure(1, weight=1)

        # Save Button
        save_button = ctk.CTkButton(tab, text="Save Stock", command=self.save_stock)
        save_button.pack(padx=20, pady=10)

    def save_stock(self):
        ticker = self.ticker_entry.get()
        shares_str = self.shares_entry.get()
        price_str = self.price_entry.get()

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
            db.add_stock(ticker, shares, purchase_price)
            messagebox.showinfo("Success", f"Stock {ticker.upper()} saved successfully.")
            # Clear the entry fields
            self.ticker_entry.delete(0, 'end')
            self.shares_entry.delete(0, 'end')
            self.price_entry.delete(0, 'end')
            # Refresh the dashboard to show the new stock
            self.refresh_dashboard()
            self.refresh_alerts_tab()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save stock: {e}")


    def setup_alerts_tab(self):
        tab = self.tab_view.tab("Alerts")

        # --- Create Alert Frame ---
        create_alert_frame = ctk.CTkFrame(tab)
        create_alert_frame.pack(pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(create_alert_frame, text="Create a New Alert", font=("Arial", 16)).pack(pady=5)

        # Stock Selection
        ctk.CTkLabel(create_alert_frame, text="Stock:").pack(pady=(5,0))
        self.alert_stock_optionmenu = ctk.CTkOptionMenu(create_alert_frame, values=[])
        self.alert_stock_optionmenu.pack(pady=5)
        
        # Alert Type
        ctk.CTkLabel(create_alert_frame, text="Alert Type:").pack(pady=(5,0))
        self.alert_type_optionmenu = ctk.CTkOptionMenu(create_alert_frame, values=["Price Drops From Recent High", "Price Rises From Recent Low"])
        self.alert_type_optionmenu.pack(pady=5)

        # Threshold
        ctk.CTkLabel(create_alert_frame, text="Threshold (%):").pack(pady=(5,0))
        self.alert_threshold_entry = ctk.CTkEntry(create_alert_frame, placeholder_text="e.g., 5")
        self.alert_threshold_entry.pack(pady=5)

        # Save Button
        save_alert_button = ctk.CTkButton(create_alert_frame, text="Save Alert", command=self.save_alert)
        save_alert_button.pack(pady=10)

        # --- Existing Alerts Frame ---
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

        # Delete Button
        delete_alert_button = ctk.CTkButton(existing_alerts_frame, text="Delete Selected Alert", command=self.delete_selected_alert)
        delete_alert_button.pack(pady=10)

        # Refresh Button
        refresh_alerts_button = ctk.CTkButton(existing_alerts_frame, text="Refresh Alerts", command=self.refresh_alerts_tab)
        refresh_alerts_button.pack(pady=10)
        
        # Load initial data
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
        # Clear existing data
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)

        # Update stock dropdown
        stocks = db.get_all_stocks()
        stock_tickers = [s[1] for s in stocks]
        self.alert_stock_optionmenu.configure(values=stock_tickers)
        if not stock_tickers:
            self.alert_stock_optionmenu.set("")

        # Populate alerts tree
        for stock in stocks:
            alerts = db.get_stock_alerts(stock[0])
            for alert in alerts:
                alert_id, alert_type, threshold_percent, is_active = alert
                status = "Active" if is_active else "Inactive"
                self.alerts_tree.insert("", "end", values=(alert_id, stock[1], alert_type, threshold_percent, status))

    def setup_settings_tab(self):
        tab = self.tab_view.tab("Settings")

        # Notification Service Selection
        ctk.CTkLabel(tab, text="Notification Service:").pack(pady=(20, 5))
        self.notification_service_optionmenu = ctk.CTkOptionMenu(
            tab, 
            values=["None", "Pushover", "Pushbullet"],
            command=self.on_notification_service_change
        )
        self.notification_service_optionmenu.pack(pady=5)

        # API Key Entry
        ctk.CTkLabel(tab, text="API Key / Access Token:").pack(pady=(10, 5))
        self.api_key_entry = ctk.CTkEntry(tab, width=300, placeholder_text="Enter your API Key or Access Token")
        self.api_key_entry.pack(pady=5)

        # Dashboard Refresh Interval
        ctk.CTkLabel(tab, text="Dashboard Refresh Interval (seconds):").pack(pady=(10, 5))
        self.refresh_interval_entry = ctk.CTkEntry(tab, width=100, placeholder_text="e.g., 300")
        self.refresh_interval_entry.pack(pady=5)

        # Save Settings Button
        save_settings_button = ctk.CTkButton(tab, text="Save Settings", command=self.save_settings)
        save_settings_button.pack(pady=20)

        # Load existing settings
        self.load_settings()

    def on_notification_service_change(self, choice):
        # This function will be called when the option menu selection changes
        # We can add logic here later if needed, e.g., to change placeholder text
        pass

    def save_settings(self):
        service = self.notification_service_optionmenu.get()
        api_key = self.api_key_entry.get()
        refresh_interval_str = self.refresh_interval_entry.get()

        try:
            refresh_interval = int(refresh_interval_str)
            if refresh_interval < 60:
                raise ValueError("Interval must be at least 60 seconds.")
        except ValueError:
            messagebox.showerror("Error", "Refresh interval must be a valid positive integer.")
            return

        try:
            db.save_setting("notification_service", service)
            db.save_setting("api_key", api_key)
            db.save_setting("dashboard_refresh_interval", str(refresh_interval))
            messagebox.showinfo("Success", "Settings saved successfully.")
            self.start_dashboard_refresh_thread() # Restart thread with new interval
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def load_settings(self):
        service = db.get_setting("notification_service")
        api_key = db.get_setting("api_key")
        refresh_interval = db.get_setting("dashboard_refresh_interval")

        if service:
            self.notification_service_optionmenu.set(service)
        if api_key:
            self.api_key_entry.delete(0, ctk.END)
            self.api_key_entry.insert(0, api_key)
        if refresh_interval:
            self.refresh_interval_entry.delete(0, ctk.END)
            self.refresh_interval_entry.insert(0, refresh_interval)

    def start_dashboard_refresh_thread(self):
        # Stop existing thread if any
        if hasattr(self, 'dashboard_refresh_thread') and self.dashboard_refresh_thread.is_alive():
            self.stop_dashboard_refresh_thread()

        interval = int(db.get_setting("dashboard_refresh_interval"))
        self.dashboard_refresh_thread = threading.Thread(target=self._dashboard_refresh_loop, args=(interval,), daemon=True)
        self.dashboard_refresh_thread.start()

    def _dashboard_refresh_loop(self, interval):
        while True:
            time.sleep(interval)
            self.refresh_dashboard()

    def stop_dashboard_refresh_thread(self):
        # This is a placeholder. Proper thread termination requires more complex signaling.
        # For now, relying on daemon=True for application exit.
        pass

if __name__ == "__main__":
    app = StockApp()
    app.mainloop()
