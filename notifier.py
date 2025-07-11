
import requests

def send_pushover_notification(user_key, api_token, title, message):
    """
    Sends a notification via Pushover.

    Args:
        user_key (str): The user's Pushover user key.
        api_token (str): The application's Pushover API token/key.
        title (str): The title of the notification.
        message (str): The body of the notification.

    Returns:
        bool: True if the notification was sent successfully, False otherwise.
    """
    try:
        url = "https://api.pushover.net/1/messages.json"
        payload = {
            "token": api_token,
            "user": user_key,
            "title": title,
            "message": message
        }
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Pushover notification: {e}")
        return False

def send_pushbullet_notification(access_token, title, body):
    """
    Sends a notification via Pushbullet.

    Args:
        access_token (str): The user's Pushbullet access token.
        title (str): The title of the notification.
        body (str): The body of the notification.

    Returns:
        bool: True if the notification was sent successfully, False otherwise.
    """
    try:
        url = "https://api.pushbullet.com/v2/pushes"
        headers = {
            "Access-Token": access_token,
            "Content-Type": "application/json"
        }
        payload = {
            "type": "note",
            "title": title,
            "body": body
        }
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Pushbullet notification: {e}")
        return False
