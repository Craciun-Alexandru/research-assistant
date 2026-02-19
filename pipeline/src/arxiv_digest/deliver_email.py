#!/usr/bin/env python3
"""
Deliver HTML digest via email using stdlib smtplib.

Usage:
    python -m arxiv_digest.deliver_email                     # Auto-detect in current/
    python -m arxiv_digest.deliver_email --html digest.html --text digest.md
"""

import argparse
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from arxiv_digest.config import CURRENT_RUN_DIR, load_delivery_config


def build_email(
    html_content: str,
    text_content: str,
    from_address: str,
    to_address: str,
    subject: str,
) -> MIMEMultipart:
    """Build a multipart/alternative email with plain text and HTML parts.

    Args:
        html_content: HTML body.
        text_content: Plain-text body (fallback).
        from_address: Sender email address.
        to_address: Recipient email address.
        subject: Email subject line.

    Returns:
        Constructed MIMEMultipart message.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = from_address
    msg["To"] = to_address
    msg["Subject"] = subject

    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    return msg


def send_email(
    message: MIMEMultipart,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
) -> bool:
    """Send an email via SMTP with STARTTLS.

    Args:
        message: The MIME message to send.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port (typically 587 for STARTTLS).
        smtp_user: SMTP username for authentication.
        smtp_password: SMTP password for authentication.

    Returns:
        True if sent successfully, False on error.
    """
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(message["From"], message["To"], message.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        print("Error: SMTP authentication failed. Check username and password.")
        return False
    except (smtplib.SMTPConnectError, ConnectionRefusedError, OSError) as e:
        print(f"Error: Could not connect to SMTP server: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"Error: SMTP error: {e}")
        return False


def deliver_email_digest(
    html_path: Path,
    text_path: Path,
    email_config: dict,
) -> bool:
    """Load digest files and send via email.

    Args:
        html_path: Path to the HTML digest file.
        text_path: Path to the Markdown (plain text) digest file.
        email_config: Dict with smtp_host, smtp_port, smtp_user,
                      smtp_password, from_address, to_address.

    Returns:
        True if delivered successfully, False on error.
    """
    html_content = html_path.read_text()
    text_content = text_path.read_text()

    # Build subject from date in filename (digest_YYYY-MM-DD.html)
    date_str = html_path.stem.replace("digest_", "")
    subject = f"arXiv Research Digest — {date_str}"

    msg = build_email(
        html_content=html_content,
        text_content=text_content,
        from_address=email_config["from_address"],
        to_address=email_config["to_address"],
        subject=subject,
    )

    print(f"Sending email to {email_config['to_address']}...")
    return send_email(
        message=msg,
        smtp_host=email_config["smtp_host"],
        smtp_port=email_config["smtp_port"],
        smtp_user=email_config["smtp_user"],
        smtp_password=email_config["smtp_password"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver digest via email")
    parser.add_argument(
        "--html",
        help="HTML digest file (default: auto-detect digest_*.html in current/)",
    )
    parser.add_argument(
        "--text",
        help="Markdown digest file (default: auto-detect digest_*.md in current/)",
    )

    args = parser.parse_args()

    # Resolve HTML path
    if args.html:
        html_path = CURRENT_RUN_DIR / args.html
    else:
        html_files = list(CURRENT_RUN_DIR.glob("digest_*.html"))
        if not html_files:
            print(f"Error: No digest_*.html files found in {CURRENT_RUN_DIR}")
            sys.exit(1)
        html_path = html_files[0]
        print(f"Auto-detected HTML: {html_path.name}")

    # Resolve text path
    if args.text:
        text_path = CURRENT_RUN_DIR / args.text
    else:
        text_files = list(CURRENT_RUN_DIR.glob("digest_*.md"))
        if not text_files:
            print(f"Error: No digest_*.md files found in {CURRENT_RUN_DIR}")
            sys.exit(1)
        text_path = text_files[0]
        print(f"Auto-detected text: {text_path.name}")

    if not html_path.exists():
        print(f"Error: File not found: {html_path}")
        sys.exit(1)
    if not text_path.exists():
        print(f"Error: File not found: {text_path}")
        sys.exit(1)

    # Load email config
    config = load_delivery_config()
    email_config = config["email"]

    if not email_config["smtp_host"] or not email_config["to_address"]:
        print("Error: Email not configured.")
        print("Run setup.sh to configure email delivery, or edit user_preferences.json.")
        sys.exit(1)

    print("=" * 60)
    print("Delivering arXiv Digest via Email")
    print("=" * 60)
    print(f"HTML: {html_path.name}")
    print(f"Text: {text_path.name}")
    print(f"To:   {email_config['to_address']}")
    print()

    success = deliver_email_digest(html_path, text_path, email_config)

    print()
    if success:
        print("✓ Email delivered successfully!")
    else:
        print("✗ Failed to deliver email")
        sys.exit(1)


if __name__ == "__main__":
    main()
