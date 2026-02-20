#!/usr/bin/env python3
"""Deliver digest via email."""

import argparse
import sys
from pathlib import Path

from arxiv_digest.config import (
    CURRENT_RUN_DIR,
    load_delivery_config,
)


def deliver_all(
    markdown_path: Path,
    html_path: Path | None,
    delivery_config: dict,
) -> bool:
    """Deliver digest via email.

    Args:
        markdown_path: Path to the Markdown digest file.
        html_path: Path to the HTML digest file (required for email).
        delivery_config: Dict from load_delivery_config().

    Returns:
        True if delivery succeeds.
    """
    if html_path is None or not html_path.exists():
        print("Error: HTML digest not found; email delivery requires an HTML file")
        return False

    from arxiv_digest.deliver_email import deliver_email_digest

    return deliver_email_digest(html_path, markdown_path, delivery_config["email"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Deliver digest via email.")
    parser.add_argument(
        "--input",
        help="Input Markdown file (default: auto-detect digest_*.md in current/)",
    )

    args = parser.parse_args()

    # Load delivery config
    config = load_delivery_config()

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
    print()

    # Deliver
    success = deliver_all(input_path, html_path, config)

    print()
    if success:
        print("✓ Digest delivered successfully!")
    else:
        print("✗ Failed to deliver digest")
        sys.exit(1)


if __name__ == "__main__":
    main()
