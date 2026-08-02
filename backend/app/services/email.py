import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import settings
from app.logger import get_logger

log = get_logger(__name__)

def send_welcome_email(to_email: str, name: str):
    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASS:
        log.warning("Gmail credentials not set — skipping welcome email")
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
        Type what you want AI to do, answer a few smart questions, and get a prompt that actually works.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.GMAIL_USER
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASS)
            server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())
        log.info(f"Welcome email sent to {to_email}")
    except smtplib.SMTPAuthenticationError:
        log.error("Gmail authentication failed — check GMAIL_USER and GMAIL_APP_PASS")
    except smtplib.SMTPException as e:
        log.error(f"Failed to send welcome email to {to_email}: {e}")

def send_reset_email(to_email: str, name: str, reset_link: str):
    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASS:
        log.warning("Gmail credentials not set — skipping reset email")
        return

    subject = "Reset your PromptCraft password"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; color: #1a1a18;">
      <h2 style="font-size: 20px; margin-bottom: 8px;">Reset your password</h2>
      <p style="color: #8a8a82; font-size: 15px; line-height: 1.6;">
        Hi {name}, we received a request to reset your PromptCraft password.
        Click the button below — this link expires in <strong>30 minutes</strong>.
      </p>
      <a href="{reset_link}"
         style="display:inline-block;margin:24px 0;padding:12px 24px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-size:14px;font-weight:500;">
        Reset Password
      </a>
      <p style="font-size:13px;color:#8a8a82;">
        If you didn't request this, you can safely ignore this email.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.GMAIL_USER
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASS)
            server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())
        log.info(f"Password reset email sent to {to_email}")
    except smtplib.SMTPAuthenticationError:
        log.error("Gmail authentication failed — check GMAIL_USER and GMAIL_APP_PASS")
    except smtplib.SMTPException as e:
        log.error(f"Failed to send reset email to {to_email}: {e}")

    if not settings.GMAIL_USER or not settings.GMAIL_APP_PASS:
        log.warning("Gmail credentials not set — skipping welcome email")
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
        Type what you want AI to do, answer a few smart questions, and get a prompt that actually works.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.GMAIL_USER
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_USER, settings.GMAIL_APP_PASS)
            server.sendmail(settings.GMAIL_USER, to_email, msg.as_string())
        log.info(f"Welcome email sent to {to_email}")
    except smtplib.SMTPAuthenticationError:
        log.error("Gmail authentication failed — check GMAIL_USER and GMAIL_APP_PASS")
    except smtplib.SMTPException as e:
        log.error(f"Failed to send welcome email to {to_email}: {e}")