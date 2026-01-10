#!/usr/bin/env python3

import sys
import os

# Add the project directory to the path
sys.path.append(os.path.dirname(__file__))

from app.core.db import get_session, create_db_and_tables
from app.models.base import User
from sqlmodel import select

def create_test_user():
    # Create tables first
    create_db_and_tables()

    session = get_session()
    try:
        # Check if user with ID 1 exists
        user = session.exec(select(User).where(User.id == 1)).first()
        if not user:
            user = User(
                id=1,  # Explicitly set ID to 1
                name="Test User",
                email="test@example.com",
                password_hash="test_password_hash"
            )
            session.add(user)
            session.commit()
            print(f"Created user with ID: {user.id}")
        else:
            print(f"User with ID 1 already exists: {user.name}")

        return user
    finally:
        session.close()


if __name__ == "__main__":
    create_test_user()
