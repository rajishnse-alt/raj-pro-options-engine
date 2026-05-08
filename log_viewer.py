"""
View captured logs from GitHub
Displays all debug dumps captured by the app
"""

import subprocess
import json
from datetime import datetime
from pathlib import Path
import re


def get_log_files():
    """Get all log files from logs directory"""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return []

    log_files = sorted(logs_dir.glob("upstox_data_dump_*.json"), reverse=True)
    return log_files


def parse_log_content(file_path):
    """Parse a log file and extract key sections"""
    with open(file_path, 'r') as f:
        content = f.read()

    sections = {
        'file': str(file_path),
        'timestamp': file_path.stem.replace('upstox_data_dump_', ''),
        'has_critical': '[CRITICAL]' in content,
        'has_data_dump': '[DATA-DUMP]' in content,
        'content': content
    }

    # Extract CRITICAL section
    critical_match = re.search(r'\[CRITICAL\](.*?)(?=\n\[|$)', content, re.DOTALL)
    if critical_match:
        sections['critical_section'] = critical_match.group(1).strip()

    # Extract DATA-DUMP section
    data_dump_match = re.search(r'\[DATA-DUMP\](.*?)(?=\n\[|$)', content, re.DOTALL)
    if data_dump_match:
        sections['data_dump_section'] = data_dump_match.group(1).strip()

    return sections


def display_latest_log():
    """Display the latest log file"""
    log_files = get_log_files()

    if not log_files:
        print("❌ No log files found in logs/ directory")
        print("\nSetup instructions:")
        print("1. Run: python log_capture.py")
        print("2. Or commit logs manually: git add logs/ && git commit -m 'Add logs' && git push")
        return

    latest = log_files[0]
    parsed = parse_log_content(latest)

    print(f"\n{'='*80}")
    print(f"📊 LATEST LOG: {parsed['timestamp']}")
    print(f"{'='*80}\n")

    # Show file location
    print(f"📁 File: {parsed['file']}")

    # Show indicators
    print(f"✓ Has [CRITICAL] dump: {parsed['has_critical']}")
    print(f"✓ Has [DATA-DUMP]: {parsed['has_data_dump']}\n")

    # Show CRITICAL section
    if parsed.get('critical_section'):
        print(f"{'='*80}")
        print("🔍 [CRITICAL] UPSTOX DATA STRUCTURE")
        print(f"{'='*80}")
        print(parsed['critical_section'][:2000])  # First 2000 chars
        if len(parsed['critical_section']) > 2000:
            print("\n... (truncated, see full file for complete output)")

    # Show DATA-DUMP section
    if parsed.get('data_dump_section'):
        print(f"\n{'='*80}")
        print("📤 [DATA-DUMP] FROM APP.PY")
        print(f"{'='*80}")
        print(parsed['data_dump_section'][:2000])
        if len(parsed['data_dump_section']) > 2000:
            print("\n... (truncated, see full file for complete output)")

    print(f"\n{'='*80}")
    print(f"View full logs at: logs/{latest.name}")
    print(f"{'='*80}\n")


def list_all_logs():
    """List all captured logs"""
    log_files = get_log_files()

    if not log_files:
        print("No log files found.")
        return

    print(f"\n{'='*80}")
    print("📋 ALL CAPTURED LOGS")
    print(f"{'='*80}\n")

    for i, log_file in enumerate(log_files, 1):
        parsed = parse_log_content(log_file)
        print(f"{i}. {parsed['timestamp']}")
        print(f"   📁 {log_file}")
        print(f"   ✓ Critical: {parsed['has_critical']}, Data-Dump: {parsed['has_data_dump']}\n")

    print(f"View with: python log_viewer.py latest")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "latest":
        display_latest_log()
    else:
        list_all_logs()
