import io
import json
import os
import re
import uuid
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
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pydantic import BaseModel
from transformers import BartTokenizer, BartForConditionalGeneration

from google_drive_helper import authenticate, create_folder, upload_file
from mongo_db_ops import store_tokens, get_folder_id, update_folder_id, get_user_id, store_oauth_state, \
    delete_oauth_state, get_oauth_state

# Load environment variables from .env file
load_dotenv()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000/")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

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

# Set the environment variable to disable HTTPS requirement for local development
# os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Google OAuth2 configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'openid', 'https://www.googleapis.com/auth/userinfo.email']
REDIRECT_URI = f"{BACKEND_URL}/oauth2callback"

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


@app.get("/")
async def home():
    return "Research AI Backend"


@app.get("/authorize")
async def authorize():
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    state = str(uuid.uuid4())  # Generate unique state for the user

    # Store the state in MongoDB
    store_oauth_state(state, user_email="temp")  # user_email can be updated later if necessary

    authorization_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state  # Include the unique state
    )
    return RedirectResponse(url=authorization_url)


@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    # Retrieve the state from the callback URL
    state = request.query_params.get('state')

    # Validate the state to ensure the OAuth flow is legitimate
    if not get_oauth_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Continue with the OAuth flow and fetch the token
    flow = Flow.from_client_config(
        CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response)

    # Save the credentials and get the user's email from the ID token
    credentials = flow.credentials
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token,
        request=google_requests.Request(),
        audience=os.environ['GOOGLE_CLIENT_ID']
    )
    user_email = id_info.get('email')
    username = user_email.split('@')[0]
    print(f"User Name: {username}")
    store_tokens(username, credentials)

    # Check if the folder ID already exists in the database; otherwise, create it
    folder_id = get_folder_id(username)
    print(f"Folder ID: {folder_id}")
    if not folder_id:
        service = authenticate(username)
        folder_id = create_folder(service, username)
        update_folder_id(username, folder_id)

    # Delete the state after it's used
    delete_oauth_state(state)

    # Redirect to the frontend with the user email and folder ID as query parameters
    frontend_url = f"{FRONTEND_URL}?user_email={user_email}&folder_id={folder_id}"
    return RedirectResponse(url=frontend_url)


@app.get("/fetch_topics")
async def fetch_topics(user_folder: str = Query(...)):
    try:
        service = authenticate(get_user_id(user_folder))
        files = service.files().list(
            q=f"'{user_folder}' in parents and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'",
            spaces='drive',
            fields='files(id, name)').execute().get('files', [])
        topics = [file['name'].replace('.xlsx', '') for file in files]
        return {"topics": topics}
    except Exception as e:
        print(f"Error while fetching topics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error fetching topics")


@app.post("/upload_pdfs")
async def upload_pdfs(files: List[UploadFile], user_folder: str, topic: str):
    service = authenticate(get_user_id(user_folder))
    for file in files:
        file_path = f"data/{file.filename}"
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        upload_file(service, file_path, user_folder)
    return {"message": "Files uploaded successfully"}


@app.post("/parse_pdfs")
async def parse_pdfs(files: List[UploadFile] = File(...), user_folder: str = Query(...), topic: str = Query(...)):
    responses = []
    for file in files:
        try:
            # Read the uploaded file into memory
            pdf_buffer = io.BytesIO(await file.read())

            # Process the PDF content from the in-memory buffer
            paper_info = parse_pdf_details(pdf_buffer)
            full_text = extract_full_text(pdf_buffer)
            paper_info["SUMMARY"], paper_info["KEY_TAKEAWAYS"] = get_summary_and_takeaways(full_text)

            # Check for existing data
            existing_data = load_existing_data(user_folder, topic)
            if any(entry['DOI'] == paper_info['DOI'] for entry in existing_data):
                continue  # Skip existing DOIs

            # Add SL_NO
            paper_info["SL_NO"] = len(existing_data) + 1

            # Save the new data
            existing_data.append(paper_info)

            # Save to Excel in memory
            excel_buffer = io.BytesIO()
            df = pd.DataFrame(existing_data)
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            excel_buffer.seek(0)

            # Upload to Google Drive
            service = authenticate(get_user_id(user_folder))
            file_metadata = {'name': f'{topic}.xlsx', 'parents': [user_folder]}
            media_body = MediaIoBaseUpload(excel_buffer,
                                           mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

            # Check if file already exists in Google Drive
            files_in_drive = service.files().list(q=f"'{user_folder}' in parents and name='{topic}.xlsx'",
                                                  spaces='drive', fields='files(id, name)').execute().get('files', [])
            if files_in_drive:
                file_id = files_in_drive[0]['id']
                service.files().update(fileId=file_id, media_body=media_body).execute()
            else:
                service.files().create(body=file_metadata, media_body=media_body).execute()

            responses.append(paper_info)
        except Exception as e:
            print(f"Error processing file {file.filename}: {e}")
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
        print(f"Error while updating entry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/existing_data")
def get_existing_data(user_folder: str = Query(...), topic: str = Query(...)):
    try:
        existing_data = load_existing_data(user_folder, topic)
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
        print(f"Error while deleting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def parse_pdf_details(file_stream):
    file_stream.seek(0)  # Reset the stream to the beginning
    with fitz.open(stream=file_stream, filetype="pdf") as pdf_reader:
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


def extract_full_text(file_stream):
    file_stream.seek(0)  # Reset the stream to the beginning
    text = ""
    with fitz.open(stream=file_stream, filetype="pdf") as pdf_reader:
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
    service = authenticate(get_user_id(user_folder))
    files = service.files().list(q=f"'{user_folder}' in parents and name = '{topic}.xlsx'", spaces='drive',
                                 fields='files(id, name)').execute().get('files', [])

    if not files:
        # If no file exists, return an empty list
        return []

    # Get the file ID and download it directly into memory
    file_id = files[0]['id']
    request = service.files().get_media(fileId=file_id)

    # Create an in-memory buffer to store the file
    file_stream = io.BytesIO()
    downloader = MediaIoBaseDownload(file_stream, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%.")

    # Move the pointer to the start of the file
    file_stream.seek(0)

    # Load the Excel file into a pandas DataFrame directly from memory
    try:
        df = pd.read_excel(file_stream)
        df = df.fillna("")  # Handle any missing values
        return df.to_dict(orient='records')
    except Exception as e:
        print(f"Error loading Excel data: {e}")
        return []


def save_to_excel(data, user_folder, topic):
    # Create the Excel file in-memory using a BytesIO buffer
    excel_buffer = io.BytesIO()
    df = pd.DataFrame(data)
    columns_order = ["SL_NO", "NAME", "YEAR", "PUBLICATION", "PAGE_NO", "SUMMARY", "ABSTRACT", "DOI", "AUTHOR",
                     "REMARKS"]
    df = df[columns_order]

    # Save the DataFrame to the in-memory Excel file
    with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    excel_buffer.seek(0)

    # Authenticate and get the Google Drive service
    service = authenticate(get_user_id(user_folder))

    # Prepare file metadata and media body for Google Drive upload
    file_metadata = {'name': f'{topic}.xlsx', 'parents': [user_folder]}
    media_body = MediaIoBaseUpload(excel_buffer,
                                   mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Check if the file already exists in Google Drive
    files_in_drive = service.files().list(q=f"'{user_folder}' in parents and name='{topic}.xlsx'", spaces='drive',
                                          fields='files(id, name)').execute().get('files', [])

    # If the file exists, update it; otherwise, create a new one
    if files_in_drive:
        file_id = files_in_drive[0]['id']
        service.files().update(fileId=file_id, media_body=media_body).execute()
    else:
        service.files().create(body=file_metadata, media_body=media_body).execute()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
