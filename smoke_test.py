#!/usr/bin/env python3
"""
Quick smoke test for the local API.
It verifies:
- /health
- /auth/create-first-user
- /auth/login
"""

import sys
import requests

BASE_URL = "http://localhost:8000"


def main():
    try:
        # Health check
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        health.raise_for_status()
        print("✅ /health:", health.json())

        # Create first user (idempotent: returns first user if it already exists)
        first_user_payload = {
            "name": "Demo User",
            "email": "demo@example.com",
            "password": "demopass123",
        }
        create = requests.post(
            f"{BASE_URL}/auth/create-first-user", json=first_user_payload, timeout=5
        )
        create.raise_for_status()
        user = create.json()
        print(f"✅ create-first-user: id={user.get('id')} email={user.get('email')}")

        # Login
        login_payload = {
            "email": first_user_payload["email"],
            "password": first_user_payload["password"],
        }
        login = requests.post(f"{BASE_URL}/auth/login", json=login_payload, timeout=5)
        login.raise_for_status()
        token = login.json().get("access_token")
        print("✅ login OK, token starts with:", token[:12] + "..." if token else "missing")

    except requests.RequestException as exc:
        print(f"❌ Smoke test failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
