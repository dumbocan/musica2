#!/usr/bin/env python3
"""
Renew YouTube cookies when authentication fails.

Usage:
    python scripts/renew_youtube_cookies.py
    python scripts/renew_youtube_cookies.py --browser firefox
    python scripts/renew_youtube_cookies.py --browser chrome
"""
import sys
import subprocess
from pathlib import Path

COOKIES_FILE = Path("/home/micasa/audio2/storage/cookies/youtube_cookies.txt")


def renew_cookies(browser="firefox"):
    """Renew YouTube cookies using yt-dlp."""
    print(f"=== Renewing YouTube cookies from {browser} ===")

    # Test with a YouTube video
    test_video = "eJO5HU_7_1w"  # The Real Slim Shady

    result = subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--cookies-from-browser", browser,
            "--cookies", str(COOKIES_FILE),
            "--dump-single-json",
            f"https://www.youtube.com/watch?v={test_video}"
        ],
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode == 0:
        print("SUCCESS: Cookies renewed successfully")
        print(f"File: {COOKIES_FILE}")

        # Show cookie summary
        try:
            lines = COOKIES_FILE.read_text().splitlines()
            yt_lines = [ln for ln in lines if "youtube.com" in ln and not ln.startswith("#")]
            print(f"YouTube cookies: {len(yt_lines)} entries")
        except Exception:
            pass

        return True
    else:
        print("FAILED: Could not renew cookies")
        print(f"Error: {result.stderr[:300] if result.stderr else 'Unknown error'}")
        return False


def check_cookies():
    """Check if cookies are expired."""
    if not COOKIES_FILE.exists():
        print("WARNING: Cookies file does not exist")
        return False

    try:
        lines = COOKIES_FILE.read_text().splitlines()

        # Check for expired SIDTS cookies
        expired = []
        for line in lines:
            if "__Secure-(1|3)PSIDTS" in line:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        expiry = int(parts[4])
                        from datetime import datetime
                        expiry_date = datetime.fromtimestamp(expiry)
                        if datetime.now() > expiry_date:
                            expired.append(f"PSIDTS expired: {expiry_date}")
                    except ValueError:
                        pass

        if expired:
            print("WARNING: Expired cookies detected:")
            for e in expired:
                print(f"  - {e}")
            return False

        print("OK: Cookies appear valid")
        return True

    except Exception as e:
        print(f"ERROR: Could not check cookies: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Renew YouTube cookies")
    parser.add_argument("--browser", default="firefox", choices=["firefox", "chrome", "brave"],
                        help="Browser to extract cookies from (default: firefox)")
    parser.add_argument("--check", action="store_true", help="Only check cookie validity")
    args = parser.parse_args()

    if args.check:
        check_cookies()
        return

    success = renew_cookies(args.browser)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
