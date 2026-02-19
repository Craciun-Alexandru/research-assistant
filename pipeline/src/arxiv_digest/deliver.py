#!/usr/bin/env python3
"""
Deliver digest via Discord, email, or both.

Usage:
    python -m arxiv_digest.deliver                   # Auto-detect, use configured channel
    python -m arxiv_digest.deliver --channel email   # Force email delivery
    python -m arxiv_digest.deliver --channel both    # Force both channels
    python -m arxiv_digest.deliver --input digest_2026-02-04.md
    python -m arxiv_digest.deliver --method split --discord-user YOUR_USER_ID
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from arxiv_digest.config import (
    CURRENT_RUN_DIR,
    DISCORD_MAX_MESSAGE_LENGTH,
    load_delivery_config,
)


def split_markdown(content: str, max_length: int = DISCORD_MAX_MESSAGE_LENGTH) -> list:
    """
    Split markdown content by '---' delimiters.

    Discord limit is 2000 chars, we use 1900 to be safe.
    Splits on '---' delimiter first, then checks if any chunk is too long.
    """
    # Split by --- delimiter
    chunks = content.split("\n---\n")

    # Clean up chunks (strip whitespace, remove empty)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]

    # Check if any chunk exceeds max_length
    final_chunks = []
    for i, chunk in enumerate(chunks):
        if len(chunk) <= max_length:
            final_chunks.append(chunk)
        else:
            # Chunk too long, need to split further
            print(f"⚠️  Warning: Section {i + 1} is {len(chunk)} chars (max {max_length})")
            print("   Splitting into sub-chunks...")

            # Split long chunk by paragraphs (double newline)
            paragraphs = chunk.split("\n\n")
            current_subchunk = []
            current_length = 0

            for para in paragraphs:
                para_length = len(para) + 2  # +2 for \n\n

                if current_length + para_length > max_length:
                    if current_subchunk:
                        final_chunks.append("\n\n".join(current_subchunk))
                    current_subchunk = [para]
                    current_length = para_length
                else:
                    current_subchunk.append(para)
                    current_length += para_length

            if current_subchunk:
                final_chunks.append("\n\n".join(current_subchunk))

    return final_chunks


def send_discord_message(message: str, user_id: str) -> bool:
    """Send message via openclaw message send command."""

    try:
        cmd = [
            "openclaw",
            "message",
            "send",
            "--channel",
            "discord",
            "--target",
            f"user:{user_id}",
            "--message",
            message,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            return True
        else:
            print("Error sending message:")
            print(f"  stderr: {result.stderr}")
            print(f"  stdout: {result.stdout}")
            return False

    except subprocess.TimeoutExpired:
        print("Error: Command timed out after 30 seconds")
        return False
    except FileNotFoundError:
        print("Error: 'openclaw' command not found")
        print("Make sure OpenClaw CLI is installed and in PATH")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def deliver_digest(markdown_path: Path, user_id: str, method: str) -> bool:
    """Deliver digest via Discord."""

    # Read markdown
    with markdown_path.open() as f:
        content = f.read()

    print(f"Content length: {len(content)} characters")

    # Method: single message
    if method == "message":
        if len(content) > 1900:
            print(f"Error: Content too large ({len(content)} chars) for single message")
            print("Use --method split instead")
            return False

        print("Sending as single message...")
        return send_discord_message(content, user_id)

    # Method: split into multiple messages (by --- delimiter)
    elif method == "split":
        if len(content) <= 1900:
            print("Content fits in one message, sending...")
            return send_discord_message(content, user_id)

        print("Splitting content by '---' delimiters...")
        chunks = split_markdown(content)
        print(f"Split into {len(chunks)} messages")

        # Send each chunk
        for i, chunk in enumerate(chunks, 1):
            print(f"Sending part {i}/{len(chunks)}... ({len(chunk)} chars)")

            # Don't add "Part X/Y" prefix - the chunks are already properly formatted
            # Just send the chunk as-is
            if not send_discord_message(chunk, user_id):
                print(f"Failed to send part {i}")
                return False

            # Small delay between messages to avoid rate limits
            if i < len(chunks):
                time.sleep(1)

        return True

    # Method: file reference only
    elif method == "file":
        date = markdown_path.stem.replace("digest_", "")
        message = f"""📚 **Your Daily arXiv Digest - {date}**

Your digest is ready at:
`{markdown_path}`

Total size: {len(content):,} characters"""

        return send_discord_message(message, user_id)

    else:
        print(f"Unknown method: {method}")
        return False


def deliver_all(
    markdown_path: Path,
    html_path: Path | None,
    delivery_config: dict,
    discord_method: str = "split",
) -> bool:
    """Dispatch delivery to discord, email, or both channels.

    Args:
        markdown_path: Path to the Markdown digest file.
        html_path: Path to the HTML digest file (required for email).
        delivery_config: Dict from load_delivery_config().
        discord_method: Discord delivery method (message/split/file).

    Returns:
        True if at least one channel succeeds.
    """
    method = delivery_config.get("method", "discord")
    any_success = False

    # Discord delivery
    if method in ("discord", "both"):
        user_id = delivery_config["discord"]["user_id"]
        print("── Discord delivery ──")
        if deliver_digest(markdown_path, user_id, discord_method):
            any_success = True
            print("✓ Discord delivery succeeded")
        else:
            print("✗ Discord delivery failed")
        print()

    # Email delivery
    if method in ("email", "both"):
        if html_path and html_path.exists():
            from arxiv_digest.deliver_email import deliver_email_digest

            print("── Email delivery ──")
            if deliver_email_digest(html_path, markdown_path, delivery_config["email"]):
                any_success = True
                print("✓ Email delivery succeeded")
            else:
                print("✗ Email delivery failed")
        else:
            print("✗ Email delivery skipped: no HTML digest found")
        print()

    return any_success


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver digest via Discord, email, or both")
    parser.add_argument(
        "--input",
        help="Input Markdown file (default: auto-detect digest_*.md in current/)",
    )
    parser.add_argument("--discord-user", help="Discord user ID (or use DISCORD_USER_ID env var)")
    parser.add_argument(
        "--method",
        choices=["message", "split", "file"],
        default="split",
        help="Discord delivery method: message (single), split (by --- delimiter), file (reference only)",
    )
    parser.add_argument(
        "--channel",
        choices=["discord", "email", "both"],
        help="Delivery channel override (default: use config from user_preferences.json)",
    )

    args = parser.parse_args()

    # Load delivery config
    config = load_delivery_config()

    # Override channel if specified
    if args.channel:
        config["method"] = args.channel

    # Override discord user if specified
    if args.discord_user:
        config["discord"]["user_id"] = args.discord_user

    # Validate discord user if needed
    if config["method"] in ("discord", "both") and not config["discord"]["user_id"]:
        print("Error: Discord user ID required")
        print("Set via --discord-user or DISCORD_USER_ID environment variable")
        sys.exit(1)

    # Resolve input path — auto-detect if not specified
    if args.input:
        input_path = CURRENT_RUN_DIR / args.input
    else:
        digest_files = list(CURRENT_RUN_DIR.glob("digest_*.md"))
        if not digest_files:
            print(f"Error: No digest_*.md files found in {CURRENT_RUN_DIR}")
            sys.exit(1)
        if len(digest_files) > 1:
            print(f"Warning: Multiple digest files found, using {digest_files[0].name}")
        input_path = digest_files[0]
        print(f"Auto-detected input: {input_path.name}\n")

    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    # Find companion HTML file
    html_path = input_path.with_suffix(".html")
    if not html_path.exists():
        html_path = None

    print("=" * 60)
    print("Delivering arXiv Digest")
    print("=" * 60)
    print(f"Markdown: {input_path.name}")
    print(f"HTML:     {html_path.name if html_path else '(not found)'}")
    print(f"Channel:  {config['method']}")
    print(f"Method:   {args.method}")
    print()

    # Deliver
    success = deliver_all(input_path, html_path, config, args.method)

    print()
    if success:
        print("✓ Digest delivered successfully!")
    else:
        print("✗ Failed to deliver digest")
        sys.exit(1)


if __name__ == "__main__":
    main()
