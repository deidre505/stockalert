  Project Design Document: Stock Alert Dashboard
   * Version: 1.0
   * Date: July 10, 2025
   * Author: Gemini

  1. Project Overview


  1.1. Mission Statement
  To create a user-friendly desktop application that allows users to monitor a custom portfolio of stocks. The application will provide a visual dashboard of stock performance, track profit/loss, and deliver timely, configurable alerts to
   both the desktop and the user's mobile device when significant price movements occur.


  1.2. Core Features
   * Portfolio Management: Add, edit, and remove stocks from a personal portfolio.
   * Dashboard & Visualization: View the total portfolio value and profit/loss. See individual stock price graphs with the average purchase price clearly marked.
   * Intelligent, Configurable Alerts: Set up alerts based on price reversals from recent highs or lows, using a percentage-based threshold.
   * Flexible Mobile Notifications: Allow users to connect their own Pushbullet or Pushover accounts to receive alerts directly on their iOS or Android devices.
   * Persistent Local Storage: All user data (portfolio, alerts, settings) will be saved locally, requiring no online account with the application itself.

  2. User Interface (UI) & Application Flow

  The application will be composed of four primary sections or pages.


  2.1. Main Dashboard
   * Purpose: The main landing page, providing an at-a-glance summary of the user's portfolio.
   * Components:
       * Portfolio Summary Card: Displays Total Portfolio Value, Total Profit/Loss ($), and Total Profit/Loss (%).
       * Stock List Table: A scrollable list of all tracked stocks with the following columns:
           * Ticker Symbol (e.g., AAPL)
           * Current Price
           * Today's Change ($ and %)
           * Number of Shares
           * Average Purchase Price
           * Total P/L for Holding ($ and %)
       * Price Chart Area: Displays a line graph of the stock selected from the table above. The time frame will be user-selectable (1D, 5D, 1M, 6M, 1Y). A horizontal line will be rendered on the chart indicating the Average Purchase
         Price if it has been provided.


  2.2. Add/Edit Stock Page
   * Purpose: A simple form for adding a new stock to the portfolio or editing an existing one.
   * Input Fields:
       * Stock Ticker Symbol (Required): The official market ticker.
       * Number of Shares (Optional): The quantity of shares owned.
       * Average Purchase Price (Optional): The cost per share.


  2.3. Alert Configuration Page
   * Purpose: To create, view, and manage all price alerts for tracked stocks.
   * Components:
       * A list of all stocks in the user's portfolio.
       * For each stock, the user can add one or more alert rules.
       * Alert Rule Setup Form:
           * Alert Type: A choice between Price Drops From Recent High and Price Rises From Recent Low.
           * Threshold (%): A numeric input for the percentage change that should trigger the alert (e.g., 5, 10).
           * Status: An on/off toggle to enable or disable the alert.


  2.4. Settings Page
   * Purpose: To configure application-wide settings, primarily for notifications.
   * Components:
       * Notification Service: A dropdown menu with three options: None, Pushover, Pushbullet.
       * API Credentials: Based on the selection above, one of the following input fields will appear:
           * Pushover User Key
           * Pushbullet Access Token
       * A "Save" button to store the settings.

  3. Technical Specifications


  3.1. Core Architecture
   * Language: Python
   * GUI Framework: A standard Python GUI library like Tkinter, PyQt, or CustomTkinter will be used to build the desktop interface.
   * Backend Logic: A Python backend will run in a separate thread to handle data fetching, alert evaluation, and notifications without freezing the UI.


  3.2. Data Source
   * API: Yahoo Finance data will be sourced using the unofficial yfinance Python library.
   * Polling Strategy: To respect API limits and avoid being blocked, the application will batch requests. It will fetch data for 5-10 symbols in a single request, with a delay of 30-60 seconds between fetch cycles.


  3.3. Alert Logic
   * Method: The "High/Low Since Last Alert" (Resetting Benchmark) method will be used.
   * Process for a "Drop from High" Alert:
       1. State 1: Watching for Peak: The app monitors the stock price, continuously updating its "peak price" variable to the highest price seen since the watch began.
       2. State 2: Watching for Drop: Once the stock price starts to fall from the established peak, the app calculates the trigger price (Peak Price - Threshold %).
       3. State 3: Alert & Reset: If the stock hits the trigger price, a notification is sent. The system then resets and returns to "State 1," waiting to establish a new, higher peak before it will watch for a drop again.
   * The logic is mirrored for "Rise from Low" alerts.


  3.4. Mobile Notifications
   * Services: Both Pushover and Pushbullet will be supported.
   * Implementation: The user must create their own account with their chosen service and provide their personal API key/token to the application via the Settings Page. The application will then use this key to send alerts. The cost of
     the service (e.g., the $5 one-time fee for Pushover) is borne by the end-user.


  3.5. Data Storage
   * Database: A local SQLite database file (portfolio.db) will be used to store all user data. This makes the application self-contained and portable.
   * Schema:
       * `stocks` table:
           * id (INTEGER, PRIMARY KEY)
           * ticker (TEXT, NOT NULL, UNIQUE)
           * shares (REAL)
           * purchase_price (REAL)
       * `alerts` table:
           * id (INTEGER, PRIMARY KEY)
           * stock_id (INTEGER, FOREIGN KEY to stocks.id)
           * alert_type (TEXT, 'drop' or 'rise')
           * threshold_percent (REAL)
           * is_active (INTEGER, 0 or 1)
           * last_benchmark_price (REAL) / Stores the last peak/trough /
           * current_state (TEXT, 'watching_for_peak' or 'watching_for_drop', etc.)
       * `settings` table: (Key-Value Store)
           * key (TEXT, PRIMARY KEY, e.g., 'notification_service', 'api_key')
           * value (TEXT)