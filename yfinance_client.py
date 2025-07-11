
import requests
import time

def get_current_prices(tickers):
    """
    Fetches the current market price for a list of stock tickers by hitting the 
    Yahoo Finance API directly.

    Args:
        tickers (list): A list of stock ticker symbols (e.g., ['AAPL', 'GOOGL']).

    Returns:
        dict: A dictionary mapping each ticker to its current price.
    """
    if not tickers:
        return {}

    prices = {}
    # Use a standard browser user-agent to avoid being blocked
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    for ticker_symbol in tickers:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_symbol}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            data = response.json()
            # The most reliable field for the current price
            current_price = data['chart']['result'][0]['meta']['regularMarketPrice']
            
            if current_price:
                prices[ticker_symbol] = current_price
            else:
                print(f"Could not find price for {ticker_symbol} in API response.")

            # Small delay to be respectful to the API
            time.sleep(0.2)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching direct for {ticker_symbol}: {e}")
        except (KeyError, IndexError) as e:
            print(f"Error parsing response for {ticker_symbol}: Invalid ticker or API change? {e}")
            
    return prices

if __name__ == '__main__':
    # Example usage:
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']
    prices = get_current_prices(test_tickers)
    
    if prices:
        for ticker, price in prices.items():
            print(f"{ticker}: ${price:.2f}")
    else:
        print("Could not fetch prices.")
