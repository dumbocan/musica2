"""
Simplified security functions using hashlib instead of bcrypt.
"""

import hashlib
import secrets
import time
from typing import Optional
from app.core.config import settings

def get_password_hash(password: str) -> str:
    """
    Hash a password using SHA-256 with a salt.
    
    Args:
        password: The password to hash
        
    Returns:
        A string containing the salt and hashed password
    """
    # Generate a random salt
    salt = secrets.token_hex(16)
    
    # Hash the password with the salt
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    
    # Return salt and hash separated by a colon
    return f"{salt}:{hashed}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: The plain password to verify
        hashed_password: The hashed password to check against
        
    Returns:
        True if the password is correct, False otherwise
    """
    try:
        # Split the salt and hash
        salt, stored_hash = hashed_password.split(":", 1)
        
        # Hash the provided password with the stored salt
        computed_hash = hashlib.sha256((plain_password + salt).encode()).hexdigest()
        
        # Compare the hashes
        return secrets.compare_digest(computed_hash, stored_hash)
    except (ValueError, AttributeError):
        return False

def create_user_token(user_id: int, email: str) -> str:
    """
    Create a signed token for the user (simple JWT-like, 24h expiry).
    """
    import base64
    import json

    exp = int(time.time()) + 24 * 60 * 60  # 24h
    payload = {"user_id": user_id, "email": email, "exp": exp}

    payload_json = json.dumps(payload)
    payload_b64 = base64.b64encode(payload_json.encode()).decode()

    secret = settings.JWT_SECRET_KEY or "secret_key"
    signature = hashlib.sha256((payload_b64 + secret).encode()).hexdigest()

    return f"{payload_b64}.{signature}"

def get_current_user_id(token: str) -> int:
    """
    Extract the user ID from a token and validate signature/expiration.
    """
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")

        payload_b64, signature = parts
        secret = settings.JWT_SECRET_KEY or "secret_key"
        expected_signature = hashlib.sha256((payload_b64 + secret).encode()).hexdigest()

        if not secrets.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature")

        import base64
        import json

        payload_json = base64.b64decode(payload_b64.encode()).decode()
        payload = json.loads(payload_json)

        now = int(time.time())
        exp = payload.get("exp")
        if exp and now > exp:
            raise ValueError("Token expired")

        return payload["user_id"]
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Invalid token: {str(e)}")
