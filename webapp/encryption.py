"""
Encryption utilities for sensitive data (API keys, access tokens)
Uses AES-256 encryption with Fernet (symmetric encryption)
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
import os
import secrets

# Generate or load encryption key
ENCRYPTION_KEY_FILE = "data/.encryption_key"
SALT_FILE = "data/.salt"


def generate_key() -> bytes:
    """
    Generate a new encryption key from a password
    
    Returns:
        Fernet encryption key
    """
    # Generate a random password for encryption
    password = secrets.token_bytes(32)
    
    # Generate or load salt
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, "rb") as f:
            salt = f.read()
    else:
        salt = os.urandom(16)
        os.makedirs("data", exist_ok=True)
        with open(SALT_FILE, "wb") as f:
            f.write(salt)
    
    # Derive key from password
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password))
    
    return key


def get_encryption_key() -> bytes:
    """
    Get or create the encryption key
    
    Returns:
        Fernet encryption key
    """
    if os.path.exists(ENCRYPTION_KEY_FILE):
        with open(ENCRYPTION_KEY_FILE, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        os.makedirs("data", exist_ok=True)
        with open(ENCRYPTION_KEY_FILE, "wb") as f:
            f.write(key)
        return key


# Global Fernet instance
_fernet = None


def get_fernet() -> Fernet:
    """Get the global Fernet encryption instance"""
    global _fernet
    if _fernet is None:
        key = get_encryption_key()
        _fernet = Fernet(key)
    return _fernet


def encrypt_data(data: str) -> str:
    """
    Encrypt sensitive data using Fernet (AES-256)
    
    Args:
        data: Plain text string to encrypt
        
    Returns:
        Base64 encoded encrypted string
    """
    if not data:
        return ""
    
    fernet = get_fernet()
    encrypted = fernet.encrypt(data.encode())
    return encrypted.decode()


def decrypt_data(encrypted_data: str) -> str:
    """
    Decrypt encrypted data
    
    Args:
        encrypted_data: Base64 encoded encrypted string
        
    Returns:
        Decrypted plain text string
    """
    if not encrypted_data:
        return ""
    
    fernet = get_fernet()
    try:
        decrypted = fernet.decrypt(encrypted_data.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Decryption error: {e}")
        return ""


def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt Zerodha API key for storage
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Encrypted API key string
    """
    return encrypt_data(api_key)


def decrypt_api_key(encrypted_api_key: str) -> str:
    """
    Decrypt Zerodha API key from storage
    
    Args:
        encrypted_api_key: Encrypted API key string
        
    Returns:
        Plain text API key
    """
    return decrypt_data(encrypted_api_key)


def encrypt_access_token(access_token: str) -> str:
    """
    Encrypt Zerodha access token for storage
    
    Args:
        access_token: Plain text access token
        
    Returns:
        Encrypted access token string
    """
    return encrypt_data(access_token)


def decrypt_access_token(encrypted_access_token: str) -> str:
    """
    Decrypt Zerodha access token from storage
    
    Args:
        encrypted_access_token: Encrypted access token string
        
    Returns:
        Plain text access token
    """
    return decrypt_data(encrypted_access_token)


# Initialize encryption on import
if __name__ == "__main__":
    # Test encryption
    print("Testing encryption...")
    
    test_data = "test_api_key_12345"
    encrypted = encrypt_api_key(test_data)
    decrypted = decrypt_api_key(encrypted)
    
    print(f"Original: {test_data}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_data == decrypted}")
    
    assert test_data == decrypted, "Encryption/decryption failed!"
    print("✅ Encryption test passed!")

