#!/usr/bin/env python3
"""
Test script for Audio2 API endpoints.
Usage: python scripts/test_api.py [endpoint]
"""

import requests
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.security import create_access_token  # noqa: E402
from app.models.base import User, get_engine  # noqa: E402
from sqlmodel import Session, select  # noqa: E402


BASE_URL = "http://localhost:8000"


def get_test_token():
    """Get or create a test token for user_id=1."""
    # Try to get user 1 from database
    engine = get_engine()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.id == 1)).first()
        if not user:
            print("❌ No user found with id=1. Create a user first via /auth/register")
            sys.exit(1)

        token = create_access_token({"user_id": user.id, "email": user.email})
        print(f"✅ Token generated for user: {user.email} (id={user.id})")
        return token


def test_health():
    """Test /health endpoint."""
    resp = requests.get(f"{BASE_URL}/health")
    print(f"GET /health -> {resp.status_code}")
    return resp.status_code == 200


def test_most_played(token):
    """Test /tracks/most-played endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/tracks/most-played", headers=headers)
    print(f"GET /tracks/most-played -> {resp.status_code}")
    if resp.status_code == 401:
        print("   ℹ️  Authentication required (expected after fix)")
    return resp.status_code


def test_recent_plays(token):
    """Test /tracks/recent-plays endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/tracks/recent-plays", headers=headers)
    print(f"GET /tracks/recent-plays -> {resp.status_code}")
    return resp.status_code


def test_record_play(token, track_id=1):
    """Test /tracks/play/{track_id} endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(f"{BASE_URL}/tracks/play/{track_id}", headers=headers)
    print(f"POST /tracks/play/{track_id} -> {resp.status_code}")
    return resp.status_code


def main():
    import argparse  # noqa: E402
    parser = argparse.ArgumentParser(description="Test Audio2 API")
    parser.add_argument("endpoint", nargs="?", choices=["health", "most-played", "recent-plays", "record-play", "all"],
                        default="all", help="Endpoint to test")
    args = parser.parse_args()

    print("🔧 Audio2 API Test Script")
    print("=" * 40)

    if args.endpoint in ["health", "all"]:
        test_health()

    if args.endpoint in ["most-played", "all"]:
        token = get_test_token()
        test_most_played(token)

    if args.endpoint in ["recent-plays", "all"]:
        token = get_test_token()
        test_recent_plays(token)

    if args.endpoint in ["record-play", "all"]:
        token = get_test_token()
        test_record_play(token)

    print("=" * 40)
    print("Done!")


if __name__ == "__main__":
    main()
