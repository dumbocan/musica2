"""
Simplified security functions using hashlib instead of bcrypt.
"""

import hashlib
import secrets
from typing import Optional

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
    Create a JWT token for the user.
    
    Args:
        user_id: The user's ID
        email: The user's email
        
    Returns:
        A JWT token string
    """
    # In a real application, this should generate a proper JWT token
    # For this simplified example, we'll create a simple token
    import base64
    import json
    
    # Create a simple token payload
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": 1800  # 30 minutes
    }
    
    # Encode the payload
    payload_json = json.dumps(payload)
    payload_b64 = base64.b64encode(payload_json.encode()).decode()
    
    # Create a simple signature (in a real app, this would be proper JWT signing)
    signature = hashlib.sha256((payload_b64 + "secret_key").encode()).hexdigest()
    
    return f"{payload_b64}.{signature}"

def get_current_user_id(token: str) -> int:
    """
    Extract the user ID from a token.
    
    Args:
        token: The JWT token
        
    Returns:
        The user ID extracted from the token
        
    Raises:
        Exception: If the token is invalid
    """
    try:
        # Split the token
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")
            
        payload_b64, signature = parts
        
        # Verify the signature
        expected_signature = hashlib.sha256((payload_b64 + "secret_key").encode()).hexdigest()
        
        if not secrets.compare_digest(signature, expected_signature):
            raise ValueError("Invalid token signature")
            
        # Decode the payload
        import base64
        import json
        
        payload_json = base64.b64decode(payload_b64.encode()).decode()
        payload = json.loads(payload_json)
        
        # In a real application, we should also check the expiration time
        
        return payload["user_id"]
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        # In a real application, this would raise an appropriate HTTP exception
        raise ValueError(f"Invalid token: {str(e)}")
