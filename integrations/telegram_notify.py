# import os
# import sys
# import requests

# BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# if not BOT_TOKEN or not CHAT_ID:
#     raise RuntimeError("Missing Telegram credentials in environment variables")

# def send_telegram_message(message: str):
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
#     payload = {
#         "chat_id": CHAT_ID,
#         "text": message,
#         "parse_mode": "Markdown"
#     }

#     response = requests.post(url, json=payload, timeout=10)
#     response.raise_for_status()


# if __name__ == "__main__":
#     """
#     Expected args:
#       argv[1] -> pipeline name
#       argv[2] -> build number
#       argv[3] -> build status (SUCCESS / FAILURE)
#       argv[4] -> build URL
#     """

#     pipeline = sys.argv[1]
#     build_number = sys.argv[2]
#     status = sys.argv[3]
#     build_url = sys.argv[4]

#     emoji = "✅" if status == "SUCCESS" else "❌"

#     message = (
#         f"{emoji} *Jenkins Pipeline Finished*\n\n"
#         f"*Pipeline:* {pipeline}\n"
#         f"*Build:* #{build_number}\n"
#         f"*Status:* {status}\n"
#         f"*URL:* {build_url}"
#     )

#     send_telegram_message(message)


#!/usr/bin/env python3
import os
import sys
import requests
import logging
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def build_status_emoji(status: str) -> str:
    status_map: Dict[str, str] = {
        "SUCCESS": "✅",
        "FAILURE": "❌",
        "UNSTABLE": "⚠️",
        "ABORTED": "⛔"
    }
    return status_map.get(status.upper(), "❓")


def build_discord_color(status: str) -> int:
    color_map = {
        "SUCCESS": 0x2ECC71,   # green
        "FAILURE": 0xE74C3C,   # red
        "UNSTABLE": 0xF1C40F,  # yellow
        "ABORTED": 0x95A5A6    # grey
    }
    return color_map.get(status.upper(), 0x3498DB)  # default blue


def send_telegram(message: str):
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    r = requests.post(TELEGRAM_API, json=payload, timeout=10)
    r.raise_for_status()
    logging.info("Telegram notification sent.")


def send_discord(pipeline: str, build_number: str, status: str, build_url: str):
    if not DISCORD_WEBHOOK_URL:
        logging.info("No Discord webhook configured. Skipping.")
        return

    embed = {
        "title": "Jenkins Pipeline Finished",
        "color": build_discord_color(status),
        "fields": [
            {"name": "Pipeline", "value": pipeline, "inline": True},
            {"name": "Build", "value": f"#{build_number}", "inline": True},
            {"name": "Status", "value": status, "inline": True},
            {"name": "URL", "value": build_url, "inline": False},
        ]
    }

    payload = {"embeds": [embed]}

    r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    r.raise_for_status()
    logging.info("Discord notification sent.")


def main():
    if len(sys.argv) != 5:
        logging.error("Invalid arguments.")
        sys.exit(1)

    pipeline = sys.argv[1]
    build_number = sys.argv[2]
    status = sys.argv[3]
    build_url = sys.argv[4]

    emoji = build_status_emoji(status)

    telegram_message = (
        f"{emoji} *Jenkins Pipeline Finished*\n\n"
        f"*Pipeline:* {pipeline}\n"
        f"*Build:* #{build_number}\n"
        f"*Status:* {status}\n"
        f"*URL:* {build_url}"
    )

    # Send notifications independently
    try:
        send_telegram(telegram_message)
    except Exception as e:
        logging.error(f"Telegram failed: {e}")

    try:
        send_discord(pipeline, build_number, status, build_url)
    except Exception as e:
        logging.error(f"Discord failed: {e}")


if __name__ == "__main__":
    main()