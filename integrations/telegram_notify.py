import os
import sys
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing Telegram credentials in environment variables")

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot8168976601:AAEaLsFSRS3PL5sKIF139z3qif9Md4nr7dY/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


if __name__ == "__main__":
    """
    Expected args:
      argv[1] -> pipeline name
      argv[2] -> build number
      argv[3] -> build status (SUCCESS / FAILURE)
      argv[4] -> build URL
    """

    pipeline = sys.argv[1]
    build_number = sys.argv[2]
    status = sys.argv[3]
    build_url = sys.argv[4]

    emoji = "✅" if status == "SUCCESS" else "❌"

    message = (
        f"{emoji} *Jenkins Pipeline Finished*\n\n"
        f"*Pipeline:* {pipeline}\n"
        f"*Build:* #{build_number}\n"
        f"*Status:* {status}\n"
        f"*URL:* {build_url}"
    )

    send_telegram_message(message)
