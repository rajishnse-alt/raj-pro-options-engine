"""
Log capture and GitHub pusher utility
Captures Streamlit debug output and auto-commits to GitHub
"""

import os
import sys
from datetime import datetime
import subprocess
import json
from pathlib import Path


class LogCapture:
    """Captures print output and writes to file + pushes to GitHub"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"upstox_data_dump_{timestamp}.json"

        self.original_stdout = sys.stdout
        self.buffer = []

    def write(self, message):
        """Intercept print output"""
        self.original_stdout.write(message)
        self.buffer.append(message)

        # Auto-save if we capture a [CRITICAL] or [DATA-DUMP] section
        if "[CRITICAL]" in message or "[DATA-DUMP]" in message:
            self.save_to_file()

    def flush(self):
        """Required by file-like interface"""
        self.original_stdout.flush()

    def save_to_file(self):
        """Save buffered output to file"""
        content = ''.join(self.buffer)
        with open(self.log_file, 'w') as f:
            f.write(content)
        print(f"\n[LOG-CAPTURE] Saved to {self.log_file}")

    def push_to_github(self, message: str = "Auto-capture: debug logs"):
        """Commit and push logs to GitHub"""
        try:
            # Save content first
            self.save_to_file()

            # Git commands
            os.chdir(self.log_dir.parent)

            subprocess.run(["git", "add", str(self.log_file)], check=True)
            subprocess.run([
                "git", "commit", "-m",
                f"{message} - {datetime.now().isoformat()}"
            ], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)

            print(f"[LOG-CAPTURE] ✓ Pushed to GitHub: {self.log_file}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"[LOG-CAPTURE] ✗ Git error: {e}")
            return False
        except Exception as e:
            print(f"[LOG-CAPTURE] ✗ Error: {e}")
            return False


# Convenience function for Streamlit app
def start_log_capture():
    """Start capturing logs in Streamlit app"""
    log_capturer = LogCapture()
    sys.stdout = log_capturer
    return log_capturer


if __name__ == "__main__":
    # Test usage
    capturer = LogCapture()
    capturer.write("[CRITICAL] Test data dump\n")
    capturer.write("Some test content\n")
    capturer.push_to_github("Test commit")
