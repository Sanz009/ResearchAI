import json
import os
import pickle
import re
from typing import List, Dict

import bibtexparser
import fitz  # PyMuPDF
import pandas as pd
import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel
from transformers import BartTokenizer, BartForConditionalGeneration

from google_drive_helper import authenticate, create_folder, upload_file, download_file

HOST_URL = f"localhost"

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# Ensure CORS middleware is configured before any routes are added
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize the summarizer
summarizer_tokenizer = BartTokenizer.from_pretrained('facebook/bart-large-cnn')
summarizer_model = BartForConditionalGeneration.from_pretrained('facebook/bart-large-cnn')

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# Set the environment variable to disable HTTPS requirement for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Google OAuth2 configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'openid', 'https://www.googleapis.com/auth/userinfo.email']
REDIRECT_URI = f"http://{HOST_URL}:8000/oauth2callback"

CLIENT_CONFIG = {
    "installed": {
        "client_id": os.getenv('GOOGLE_CLIENT_ID'),
        "client_secret": os.getenv('GOOGLE_CLIENT_SECRET'),
        "project_id": os.getenv('GOOGLE_PROJECT_ID'),
        "redirect_uris": json.loads(os.getenv('GOOGLE_REDIRECT_URIS')),
        "auth_uri": os.getenv('GOOGLE_AUTH_URI', "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv('GOOGLE_TOKEN_URI', "https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.getenv('GOOGLE_AUTH_PROVIDER_CERT_URL',
                                                 "https://www.googleapis.com/oauth2/v1/certs")
    }
}


class DeleteRequest(BaseModel):
    no: int


@app.get("/authorize")
def authorize():
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Use 'consent' to ensure a fresh login every time
    )
    # Save the state so the callback can verify the auth server response
    with open("state.txt", "w") as state_file:
        state_file.write(state)
    return RedirectResponse(url=authorization_url)


@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    state = open("state.txt", "r").read()
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response)

    # Save the credentials for later use
    credentials = flow.credentials
    with open("token.pickle", "wb") as token:
        pickle.dump(credentials, token)

    # Get user info
    if credentials.id_token is None:
        raise HTTPException(status_code=400, detail="ID token is missing")

    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token,
        request=google_requests.Request(),
        audience=os.environ['GOOGLE_CLIENT_ID']
    )
    user_email = id_info.get('email')
    print(f"User Email -> {user_email}")
    username = user_email.split('@')[0]

    # Check if user folder already exists, otherwise create it
    user_folder_mapping_path = 'user_folder_mapping.json'
    if os.path.exists(user_folder_mapping_path):
        with open(user_folder_mapping_path, 'r') as f:
            user_folder_mapping = json.load(f)
    else:
        user_folder_mapping = {}

    if username not in user_folder_mapping:
        service = authenticate()
        folder_id = create_folder(service, username)
        user_folder_mapping[username] = folder_id
        with open(user_folder_mapping_path, 'w') as f:
            json.dump(user_folder_mapping, f)
    else:
        folder_id = user_folder_mapping[username]

    # Clean up any previous user's data in the local data directory
    cleanup_local_data()

    # Redirect to frontend with user email and folder ID as query parameters
    frontend_url = f"http://{HOST_URL}:3000?user_email={user_email}&folder_id={folder_id}"
    return RedirectResponse(url=frontend_url)


@app.get("/fetch_topics")
async def fetch_topics(user_folder: str = Query(...)):
    try:
        service = authenticate()
        files = service.files().list(
            q=f"'{user_folder}' in parents and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'",
            spaces='drive',
            fields='files(id, name)').execute().get('files', [])
        topics = [file['name'].replace('.xlsx', '') for file in files]
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error fetching topics")


@app.post("/upload_pdfs")
async def upload_pdfs(files: List[UploadFile], user_folder: str, topic: str):
    service = authenticate()
    for file in files:
        file_path = f"data/{file.filename}"
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        upload_file(service, file_path, user_folder)
    return {"message": "Files uploaded successfully"}


@app.post("/parse_pdfs")
async def parse_pdfs(files: List[UploadFile] = File(...), user_folder: str = Query(...), topic: str = Query(...)):
    responses = []
    topic_file_path = os.path.join(DATA_DIR, f"{topic}.xlsx")
    for file in files:
        file_path = os.path.join(DATA_DIR, file.filename)
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())

            paper_info = parse_pdf_details(file_path)
            full_text = extract_full_text(file_path)
            paper_info["SUMMARY"], paper_info["KEY_TAKEAWAYS"] = get_summary_and_takeaways(full_text)

            # Check for existing data
            existing_data = load_existing_data(user_folder, topic)
            if any(entry['DOI'] == paper_info['DOI'] for entry in existing_data):
                continue  # Skip existing DOIs

            # Add SL_NO
            paper_info["SL_NO"] = len(existing_data) + 1

            # Save the new data
            existing_data.append(paper_info)
            save_to_excel(existing_data, user_folder, topic)

            responses.append(paper_info)
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    return responses


@app.post("/fetch_by_dois")
async def fetch_by_dois(dois: List[str], user_folder: str = Query(...), topic: str = Query(...)):
    responses = []
    existing_data = load_existing_data(user_folder, topic)
    for doi in dois:
        if any(entry['DOI'] == doi for entry in existing_data):
            continue  # Skip existing DOIs

        bibtex_data = get_doi_bibtex(doi)
        if not bibtex_data:
            continue

        metadata = bibtex_to_json(bibtex_data)[0]
        paper_info = {
            "NAME": metadata.get("title", "Unknown"),
            "YEAR": metadata.get("year", "Unknown"),
            "PUBLICATION": metadata.get("journal", "Unknown"),
            "PAGE_NO": metadata.get("pages", "Unknown"),
            "ABSTRACT": metadata.get("abstract", "Unknown"),
            "DOI": metadata.get("doi", "Unknown"),
            "AUTHOR": metadata.get("author", "Unknown"),
            "REMARKS": ""
        }

        # Add SL_NO
        paper_info["SL_NO"] = len(existing_data) + 1

        # Save the new data
        existing_data.append(paper_info)
        save_to_excel(existing_data, user_folder, topic)

        responses.append(paper_info)
    return responses


@app.post("/update_entry")
async def update_entry(entry: Dict, user_folder: str = Query(...), topic: str = Query(...)):
    try:
        existing_data = load_existing_data(user_folder, topic)
        for index, item in enumerate(existing_data):
            if item["SL_NO"] == entry["SL_NO"]:
                existing_data[index].update(entry)
                save_to_excel(existing_data, user_folder, topic)
                return {"message": "Entry updated successfully"}
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/existing_data")
def get_existing_data(user_folder: str = Query(...), topic: str = Query(...)):
    try:
        print(f"Getting existing data for {user_folder}, topic: {topic}")
        existing_data = load_existing_data(user_folder, topic)
        print(f"Loaded existing data: {existing_data}")
        return existing_data
    except Exception as e:
        print(f"Error loading existing data: {e}")
        raise HTTPException(status_code=500, detail="Error loading existing data")


@app.delete("/delete_entry")
async def delete_entry(request: DeleteRequest, user_folder: str = Query(...), topic: str = Query(...)):
    try:
        existing_data = load_existing_data(user_folder, topic)
        updated_data = [entry for entry in existing_data if entry["SL_NO"] != request.no]

        # Reindex SL_NO
        for i, entry in enumerate(updated_data):
            entry["SL_NO"] = i + 1

        if not updated_data:
            updated_data = pd.DataFrame(
                columns=["SL_NO", "NAME", "YEAR", "PUBLICATION", "PAGE_NO", "SUMMARY", "ABSTRACT", "DOI", "AUTHOR",
                         "REMARKS"])
        save_to_excel(updated_data, user_folder, topic)
        return {"message": "Entry deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def parse_pdf_details(file_path):
    with fitz.open(file_path) as pdf_reader:
        text = ""
        for page_num in range(pdf_reader.page_count):
            page = pdf_reader.load_page(page_num)
            text += page.get_text()

    doi = extract_doi(text)
    bibtex_data = get_doi_bibtex(doi)
    metadata = bibtex_to_json(bibtex_data)[0]

    return {
        "NAME": metadata.get("title", "Unknown"),
        "YEAR": metadata.get("year", "Unknown"),
        "PUBLICATION": metadata.get("journal", "Unknown"),
        "PAGE_NO": metadata.get("pages", "Unknown"),
        "ABSTRACT": metadata.get("abstract", "Unknown"),
        "DOI": metadata.get("doi", "Unknown"),
        "AUTHOR": metadata.get("author", "Unknown"),
        "REMARKS": ""
    }


def extract_full_text(file_path):
    text = ""
    with fitz.open(file_path) as pdf_reader:
        for page_num in range(pdf_reader.page_count):
            page = pdf_reader.load_page(page_num)
            text += page.get_text()
    return text


def extract_doi(text):
    doi_pattern = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b', re.IGNORECASE)
    match = doi_pattern.search(text)
    if match:
        return match.group(0).strip()
    return "Unknown"


def get_doi_bibtex(doi):
    base_url = f"https://doi.org/{doi}"
    headers = {
        "Accept": "text/bibliography; style=bibtex"
    }
    response = requests.get(base_url, headers=headers)
    if response.status_code == 200:
        bibtex_str = response.text.strip()
        bibtex_str = bibtex_str.encode('latin1', errors='ignore').decode('utf-8',
                                                                         errors='ignore')  # Decode using Latin-1, then re-encode as UTF-8
        return bibtex_str
    else:
        return None


def bibtex_to_json(bibtex_str):
    bib_database = bibtexparser.loads(bibtex_str)
    return json.loads(json.dumps(bib_database.entries))


def get_summary_and_takeaways(text):
    inputs = summarizer_tokenizer.batch_encode_plus([text], max_length=1024, return_tensors='pt', truncation=True)
    summary_ids = summarizer_model.generate(inputs['input_ids'], num_beams=4, max_length=150, early_stopping=True)
    summary = summarizer_tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    key_takeaways = summary  # For simplicity, using the summary as key takeaways
    return summary, key_takeaways


def load_existing_data(user_folder, topic):
    service = authenticate()
    files = service.files().list(q=f"'{user_folder}' in parents and name = '{topic}.xlsx'", spaces='drive',
                                 fields='files(id, name)').execute().get('files', [])
    topic_file_path = os.path.join(DATA_DIR, f"{topic}.xlsx")
    if files:
        file_id = files[0]['id']
        download_file(service, file_id, topic_file_path)
    try:
        df = pd.read_excel(topic_file_path)
        df = df.fillna("")
        return df.to_dict(orient='records')
    except FileNotFoundError:
        return []


def save_to_excel(data, user_folder, topic):
    df = pd.DataFrame(data)
    columns_order = ["SL_NO", "NAME", "YEAR", "PUBLICATION", "PAGE_NO", "SUMMARY", "ABSTRACT", "DOI", "AUTHOR",
                     "REMARKS"]
    df = df[columns_order]

    # Use a consistent file name for the topic
    topic_file_name = f"{topic}.xlsx"
    topic_file_path = os.path.join(DATA_DIR, topic_file_name)

    # Save the DataFrame to Excel
    df.to_excel(topic_file_path, index=False)

    # Upload the file to Google Drive
    service = authenticate()
    files = service.files().list(q=f"'{user_folder}' in parents and name='{topic_file_name}'", spaces='drive',
                                 fields='files(id, name)').execute().get('files', [])

    if files:
        # File already exists, update it
        file_id = files[0]['id']
        service.files().update(fileId=file_id, media_body=topic_file_path).execute()
    else:
        # File doesn't exist, create a new one
        upload_file(service, topic_file_path, user_folder)


def cleanup_local_data():
    if os.path.exists(DATA_DIR):
        for file in os.listdir(DATA_DIR):
            file_path = os.path.join(DATA_DIR, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error removing file {file_path}: {e}")


if __name__ == '__main__':
    cleanup_local_data()
    uvicorn.run(app, host='0.0.0.0', port=8000)
