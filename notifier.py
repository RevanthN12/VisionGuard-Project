"""
notifier.py — External Alert Notification Module
Handles sending Email (Gmail SMTP) and WhatsApp (CallMeBot API).
"""

import os
import smtplib
import urllib.request
import urllib.parse
from email.message import EmailMessage
import urllib.parse
from email.message import EmailMessage
from dotenv import load_dotenv
# pywhatkit will be imported lazily to prevent crashes if internet is down on startup
import pyautogui
import time

# Load environment variables from .env file
load_dotenv()

# ── Gmail Configuration ────────────────────────────────────────────────────────
GMAIL_SENDER    = os.getenv("GMAIL_SENDER_EMAIL",    "").strip()
GMAIL_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD",    "").strip()
GMAIL_RECIPIENT = os.getenv("ALERT_RECIPIENT_EMAIL", "").strip()

# ── Telegram Configuration ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "").strip()


# ── Email Alert ───────────────────────────────────────────────────────────────

def send_email_alert(subject: str, message_body: str,
                     attachments: list = None) -> bool:
    """
    Sends an email alert using Gmail SMTP (App Password required).
    Returns True if successful, False otherwise.
    """
    if not all([GMAIL_SENDER, GMAIL_PASSWORD, GMAIL_RECIPIENT]):
        print("[Notifier] [WARNING] Email credentials missing in .env - skipping email.")
        print("           Set GMAIL_SENDER_EMAIL, GMAIL_APP_PASSWORD, ALERT_RECIPIENT_EMAIL")
        return False

    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From']    = GMAIL_SENDER
        msg['To']      = GMAIL_RECIPIENT
        msg.set_content(message_body)

        # Attach evidence files if provided
        if attachments:
            for path in attachments:
                if path and os.path.exists(path):
                    with open(path, 'rb') as f:
                        file_data = f.read()
                    if path.lower().endswith(('.jpg', '.jpeg', '.png')):
                        subtype = 'jpeg' if path.lower().endswith(('.jpg', '.jpeg')) else 'png'
                        msg.add_attachment(file_data, maintype='image', subtype=subtype,
                                           filename=os.path.basename(path))
                    elif path.lower().endswith('.pdf'):
                        msg.add_attachment(file_data, maintype='application', subtype='pdf',
                                           filename=os.path.basename(path))
                    else:
                        msg.add_attachment(file_data, maintype='application', subtype='octet-stream',
                                           filename=os.path.basename(path))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_PASSWORD)
            smtp.send_message(msg)

        print(f"[Notifier] [SUCCESS] Email sent to {GMAIL_RECIPIENT}")
        return True

    except Exception as e:
        print(f"[Notifier] [FAILED] Email failed: {e}")
        return False


def send_telegram_alert(message: str, image_path: str = None) -> bool:
    """
    Sends a Telegram message using the Telegram Bot API.
    """
    import requests
    
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Notifier] Telegram credentials missing. Skipping alert.")
        return False
        
    chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_ID.split(',') if cid.strip()]
    overall_success = True
    
    for chat_id in chat_ids:
        try:
            print(f"[Notifier] Sending Telegram alert to {chat_id}...")
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {"chat_id": chat_id, "text": message}
            
            # Send text message
            response = requests.post(url, data=data)
            
            # Send photo if provided
            if image_path and os.path.exists(image_path) and os.path.getsize(image_path) > 1000:
                photo_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                with open(image_path, 'rb') as photo:
                    files = {'photo': photo}
                    data_photo = {'chat_id': chat_id}
                    requests.post(photo_url, data=data_photo, files=files)
                    
            if response.status_code == 200:
                print(f"[Notifier] [SUCCESS] Telegram alert sent to {chat_id} successfully!")
            else:
                print(f"[Notifier] Telegram API error for {chat_id}: {response.text}")
                overall_success = False
                
        except Exception as e:
            print(f"[Notifier] Telegram automation error for {chat_id}: {e}")
            overall_success = False
            
    return overall_success
