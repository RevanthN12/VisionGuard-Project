"""
Test script for the Email and WhatsApp Notifier
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import notifier

def main():
    print("=" * 40)
    print("Vision Guard - External Alert Test")
    print("=" * 40)
    print("\nSending Test Email...")
    email_ok = notifier.send_email_alert(
        subject="VISION GUARD TEST ALERT",
        message_body="This is a test alert from Vision Guard.\nStatus: SYSTEM ONLINE.",
        attachment_path=None
    )
    if email_ok:
        print("-> Email test PASSED.")
    else:
        print("-> Email test FAILED. Please check your .env credentials.")

    print("\nSending Test WhatsApp...")
    whatsapp_ok = notifier.send_whatsapp_alert(
        message="*VISION GUARD TEST ALERT*\nThis is a test message. Please ignore."
    )
    if whatsapp_ok:
        print("-> WhatsApp test PASSED.")
    else:
        print("-> WhatsApp test FAILED. Please check your .env credentials.")

    print("\nTest completed.")

if __name__ == "__main__":
    main()
