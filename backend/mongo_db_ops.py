import datetime
import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from pymongo import MongoClient
from crypto_ops import encrypt_token, decrypt_token

load_dotenv()

# Initialize MongoDB client
client = MongoClient(os.getenv("MONGO_URI"))
db = client.research_ai

# =================== TOKEN OPERATIONS ===================
def store_tokens(user_name, credentials):
    print(f"Storing token for {user_name}")
    access_token_encrypted = encrypt_token(credentials.token)
    refresh_token_encrypted = encrypt_token(credentials.refresh_token)

    token_data = {
        "user_email": user_name,
        "access_token": access_token_encrypted,
        "refresh_token": refresh_token_encrypted,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None
    }

    db.tokens.update_one(
        {"user_email": user_name},
        {"$set": token_data},
        upsert=True
    )

def get_tokens(user_name):
    user_data = db.tokens.find_one({"user_email": user_name})
    if not user_data:
        raise Exception("User not found")

    # Decrypt the tokens
    access_token = decrypt_token(user_data['access_token'])
    refresh_token = decrypt_token(user_data['refresh_token'])
    expiry = user_data['expiry']

    # Create credentials object
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        expiry=datetime.datetime.fromisoformat(expiry) if expiry else None
    )

    # Refresh the token if expired
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        # Update MongoDB with the new tokens
        store_tokens(user_name, credentials)

    return credentials

# =================== FOLDER MAPPING OPERATIONS ===================
def get_folder_id(user_email):
    folder_data = db.folder_mapping.find_one({"user_email": user_email})
    if folder_data:
        return folder_data["folder_id"]
    return None

def get_user_id(folder_id):
    folder_data = db.folder_mapping.find_one({"folder_id": folder_id})
    if folder_data:
        return folder_data["user_email"]
    return None

def update_folder_id(user_email, folder_id):
    db.folder_mapping.update_one(
        {"user_email": user_email},
        {"$set": {"folder_id": folder_id}},
        upsert=True
    )
    print(f"Folder ID updated for user: {user_email}")

# =================== OAUTH STATE OPERATIONS ===================
def store_oauth_state(state, user_email):
    """
    Stores the OAuth state in MongoDB, with an optional expiration for security.
    """
    state_data = {
        "state": state,
        "user_email": user_email,
        "created_at": datetime.datetime.utcnow(),
        "expires_at": datetime.datetime.utcnow() + datetime.timedelta(minutes=10)  # Optional expiration
    }
    db.oauth_states.insert_one(state_data)
    print(f"OAuth state stored for user: {user_email}")

def get_oauth_state(state):
    """
    Retrieves the OAuth state from MongoDB and checks for expiration.
    """
    state_data = db.oauth_states.find_one({"state": state})
    if not state_data:
        return None

    # Check if the state has expired
    if state_data["expires_at"] < datetime.datetime.utcnow():
        db.oauth_states.delete_one({"state": state})
        return None

    return state_data["user_email"]

def delete_oauth_state(state):
    """
    Deletes the OAuth state after it is used.
    """
    db.oauth_states.delete_one({"state": state})
    print(f"OAuth state deleted for state: {state}")
