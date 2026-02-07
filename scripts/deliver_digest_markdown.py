#!/usr/bin/env python3
"""
Deliver markdown digest via Discord using openclaw message send.

Usage:
    python3 deliver_digest_markdown.py \\
        --input digest_2026-02-04.md \\
        --discord-user YOUR_USER_ID
"""

import argparse
import os
import sys
import subprocess
import time
from pathlib import Path


def split_markdown(content: str, max_length: int = 1900) -> list:
    """
    Split markdown content by '---' delimiters.
    
    Discord limit is 2000 chars, we use 1900 to be safe.
    Splits on '---' delimiter first, then checks if any chunk is too long.
    """
    # Split by --- delimiter
    chunks = content.split('\n---\n')
    
    # Clean up chunks (strip whitespace, remove empty)
    chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
    
    # Check if any chunk exceeds max_length
    final_chunks = []
    for i, chunk in enumerate(chunks):
        if len(chunk) <= max_length:
            final_chunks.append(chunk)
        else:
            # Chunk too long, need to split further
            print(f"⚠️  Warning: Section {i+1} is {len(chunk)} chars (max {max_length})")
            print(f"   Splitting into sub-chunks...")
            
            # Split long chunk by paragraphs (double newline)
            paragraphs = chunk.split('\n\n')
            current_subchunk = []
            current_length = 0
            
            for para in paragraphs:
                para_length = len(para) + 2  # +2 for \n\n
                
                if current_length + para_length > max_length:
                    if current_subchunk:
                        final_chunks.append('\n\n'.join(current_subchunk))
                    current_subchunk = [para]
                    current_length = para_length
                else:
                    current_subchunk.append(para)
                    current_length += para_length
            
            if current_subchunk:
                final_chunks.append('\n\n'.join(current_subchunk))
    
    return final_chunks


def send_discord_message(message: str, user_id: str) -> bool:
    """Send message via openclaw message send command."""
    
    try:
        cmd = [
            'openclaw', 'message', 'send',
            '--channel', 'discord',
            '--target', f'user:{user_id}',
            '--message', message
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return True
        else:
            print(f"Error sending message:")
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
    with open(markdown_path) as f:
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
        
        print(f"Splitting content by '---' delimiters...")
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
        date = markdown_path.stem.replace('digest_', '')
        message = f"""📚 **Your Daily arXiv Digest - {date}**

Your digest is ready at:
`{markdown_path}`

Total size: {len(content):,} characters"""
        
        return send_discord_message(message, user_id)
    
    else:
        print(f"Unknown method: {method}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Deliver Markdown digest via Discord")
    parser.add_argument(
        "--input",
        required=True,
        help="Input Markdown file (e.g., digest_2026-02-04.md)"
    )
    parser.add_argument(
        "--discord-user",
        help="Discord user ID (or use DISCORD_USER_ID env var)"
    )
    parser.add_argument(
        "--method",
        choices=["message", "split", "file"],
        default="split",
        help="Delivery method: message (single), split (by --- delimiter), file (reference only)"
    )
    
    args = parser.parse_args()
    
    # Get Discord user ID
    user_id = args.discord_user or os.environ.get('DISCORD_USER_ID')
    if not user_id:
        print("Error: Discord user ID required")
        print("Set via --discord-user or DISCORD_USER_ID environment variable")
        sys.exit(1)
    
    # Resolve path
    workspace = Path.home() / ".openclaw/workspaces/research-assistant"
    input_path = workspace / "resources/digests" / args.input
    
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("Delivering arXiv Digest via Discord")
    print("=" * 60)
    print(f"File: {input_path.name}")
    print(f"User: {user_id}")
    print(f"Method: {args.method}")
    print()
    
    # Deliver
    success = deliver_digest(input_path, user_id, args.method)
    
    print()
    if success:
        print("✓ Digest delivered successfully!")
    else:
        print("✗ Failed to deliver digest")
        sys.exit(1)


if __name__ == "__main__":
    main()
