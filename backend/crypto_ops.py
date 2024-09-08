import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Key generation (do this once and save it securely)
# key = Fernet.generate_key()
# Save the key in an environment variable
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
cipher = Fernet(ENCRYPTION_KEY)


# Encrypt the token
def encrypt_token(token: str):
    return cipher.encrypt(token.encode())


# Decrypt the token
def decrypt_token(encrypted_token: str):
    return cipher.decrypt(encrypted_token).decode()
