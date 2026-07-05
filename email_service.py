import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER     = os.getenv("GMAIL_USER")
GMAIL_APP_PASS = os.getenv("GMAIL_APP_PASS")


def send_welcome_email(to_email: str, name: str):
    if not GMAIL_USER or not GMAIL_APP_PASS:
        print("Gmail credentials not set — skipping welcome email.")
        return

    subject = "Welcome to PromptCraft ✦"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; color: #1a1a18;">
      <h2 style="font-size: 22px; margin-bottom: 8px;">Welcome, {name}! ✦</h2>
      <p style="color: #8a8a82; font-size: 15px; line-height: 1.6;">
        You're now on PromptCraft — the tool that turns rough ideas into powerful AI prompts.
      </p>
      <hr style="border: none; border-top: 1px solid #e4e4e0; margin: 24px 0;" />
      <p style="font-size: 13px; color: #8a8a82;">
        Just type what you want AI to do, answer a few smart questions, and get a prompt that actually works.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"Welcome email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")