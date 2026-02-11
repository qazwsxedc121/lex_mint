#!/usr/bin/env python3
"""
Check for duplicate session IDs in conversations directory
"""
import os
import yaml
from pathlib import Path
from collections import Counter

def check_duplicates():
    """Check for duplicate session IDs in markdown files."""
    conversations_dir = Path("conversations")

    if not conversations_dir.exists():
        print("No conversations directory found")
        return

    session_ids = []

    for md_file in conversations_dir.glob("*.md"):
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract frontmatter
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        session_id = frontmatter.get('session_id')
                        if session_id:
                            session_ids.append((session_id, md_file.name))
        except Exception as e:
            print(f"Error reading {md_file}: {e}")

    # Check for duplicates
    id_counts = Counter([sid for sid, _ in session_ids])
    duplicates = {sid: count for sid, count in id_counts.items() if count > 1}

    if duplicates:
        print("DUPLICATE SESSION IDs FOUND:")
        print("=" * 50)
        for session_id, count in duplicates.items():
            print(f"\nSession ID: {session_id}")
            print(f"Appears {count} times in:")
            for sid, filename in session_ids:
                if sid == session_id:
                    print(f"  - {filename}")
    else:
        print("No duplicate session IDs found.")
        print(f"Total sessions checked: {len(session_ids)}")

if __name__ == "__main__":
    check_duplicates()
