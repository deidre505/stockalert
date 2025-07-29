
# Stock Alert Application - Design Document

This document outlines the design and architecture of the Stock Alert application, a desktop tool for monitoring stock prices and receiving alerts based on user-defined criteria.

## 1. Core Features

*   **Stock Portfolio Management:** Users can add, remove, and view stocks in their portfolio. The application tracks the number of shares, purchase price, and currency for each stock.
*   **Real-time Price Tracking:** The application fetches and displays real-time stock prices from Yahoo Finance.
*   **Customizable Alerts:** Users can set up various types of alerts for their stocks:
    *   **Price Rises Above:** Triggers when a stock's price surpasses a specific target.
    *   **Price Falls Below:** Triggers when a stock's price drops below a specific target.
    *   **Price Drops From Recent High:** Triggers when a stock's price falls by a certain percentage from its recent peak.
    *   **Price Rises From Recent Low:** Triggers when a stock's price increases by a certain percentage from its recent trough.
*   **Notifications:** The application provides both on-screen and mobile push notifications (via Pushover or Pushbullet) when an alert is triggered.
*   **GUI Dashboard:** A user-friendly graphical interface built with CustomTkinter displays the stock portfolio, performance metrics (P/L, P/L %), and alert configurations.
*   **System Tray Integration:** The application can be minimized to the system tray to run in the background.

## 2. Architecture

The application follows a modular architecture, with distinct components responsible for different functionalities.

### 2.1. Main Application (`main.py`)

*   **Framework:** CustomTkinter for the GUI.
*   **Responsibilities:**
    *   Initializes the main application window and its tabs (Dashboard, Add Stock, Alerts, Settings).
    *   Manages the overall application state (`is_running`, `is_quitting`).
    *   Handles user interactions with the GUI, such as adding stocks, creating alerts, and configuring settings.
    *   Starts and stops background threads for the alerter and dashboard refresh.
    *   Manages the system tray icon and its behavior.
    *   Includes a debug panel (accessible via `Ctrl+Shift+D`) for injecting fake price data to test alerts.

### 2.2. Alerter (`alerter.py`)

*   **Responsibilities:**
    *   Runs in a separate background thread to continuously check for alert conditions.
    *   Fetches all active alerts from the database.
    *   Retrieves live stock prices using the `yfinance_client`.
    *   Processes each alert based on its type and the current stock price.
    *   Maintains the state for percentage-based alerts (e.g., "watching_for_peak", "watching_for_drop").
    *   Sends notifications via the `notifier` module when an alert is triggered.
    *   Uses a queue (`ui_alert_queue`) to communicate triggered alerts to the main UI thread for on-screen display.

### 2.3. Database (`database.py`)

*   **Framework:** SQLite.
*   **Responsibilities:**
    *   Manages the application's data persistence. The database file is stored in the user's `APPDATA` directory.
    *   Defines the database schema, including tables for `stocks`, `alerts`, and `settings`.
    *   Provides functions for all CRUD (Create, Read, Update, Delete) operations on stocks, alerts, and settings.
    *   Handles database schema migrations to add new columns as the application evolves.

### 2.4. Yahoo Finance Client (`yfinance_client.py`)

*   **Framework:** `requests` library (directly calls the Yahoo Finance API).
*   **Responsibilities:**
    *   Fetches real-time stock price data.
    *   Includes error handling and retries for API requests.
    *   Caches API responses to improve performance and reduce the number of API calls.

### 2.5. Notifier (`notifier.py`)

*   **Framework:** `requests` library.
*   **Responsibilities:**
    *   Sends push notifications to mobile devices using third-party services.
    *   Supports Pushover and Pushbullet.
    *   Handles the API calls to these services.

## 3. Data Model

The application's data is stored in a SQLite database with the following tables:

### `stocks` table

| Column         | Type    | Description                               |
| -------------- | ------- | ----------------------------------------- |
| `id`           | INTEGER | Primary Key                               |
| `ticker`       | TEXT    | Stock ticker symbol (e.g., "AAPL")        |
| `full_name`    | TEXT    | Full name of the stock                    |
| `shares`       | REAL    | Number of shares owned                    |
| `purchase_price`| REAL    | Average purchase price per share          |
| `currency`     | TEXT    | Currency of the stock (e.g., "USD")       |

### `alerts` table

| Column                 | Type    | Description                                                                 |
| ---------------------- | ------- | --------------------------------------------------------------------------- |
| `id`                   | INTEGER | Primary Key                                                                 |
| `stock_id`             | INTEGER | Foreign key referencing the `stocks` table                                  |
| `alert_type`           | TEXT    | Type of alert (e.g., "Price Rises Above")                                   |
| `threshold_percent`    | REAL    | Percentage for dynamic alerts                                               |
| `target_price`         | REAL    | Specific price for target-based alerts                                      |
| `is_active`            | INTEGER | Flag indicating if the alert is currently active (1 for active, 0 for inactive) |
| `last_benchmark_price` | REAL    | The last recorded high/low price for percentage-based alerts                |
| `current_state`        | TEXT    | The current state of the alert (e.g., "watching_for_peak")                  |

### `settings` table

A key-value store for application settings.

| Key                        | Value                                                              |
| -------------------------- | ------------------------------------------------------------------ |
| `notification_service`     | "None", "Pushover", or "Pushbullet"                                |
| `pushover_user_key`        | User's Pushover key                                                |
| `pushover_api_token`       | Application's Pushover API token                                   |
| `pushbullet_api_token`     | User's Pushbullet access token                                     |
| `dashboard_refresh_interval`| Interval in seconds for refreshing the dashboard data              |
| `minimize_to_tray`         | "True" or "False"                                                  |
| `column_widths`            | JSON string of the dashboard table's column widths                 |

## 4. Dependencies

The application relies on the following Python libraries (as listed in `requirements.txt`):

*   `yfinance`: For fetching stock data.
*   `requests`: For making HTTP requests to notification service APIs.
*   `customtkinter`: For the graphical user interface.
*   `requests-cache`: For caching API responses.
*   `pystray`: For system tray integration.
*   `Pillow`: For handling the application icon.
