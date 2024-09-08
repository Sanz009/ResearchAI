# ResearchAI

## Overview

**ResearchAI** is a powerful AI-driven research management tool that simplifies managing, summarizing, and organizing research papers. It integrates with **Google Drive**, providing seamless authentication using **Google OAuth2** and storage for research topics and articles. ResearchAI uses **FastAPI** for a robust backend with AI models such as **BART** for summarization. Built to serve researchers, scholars, and academics, it assists in parsing PDFs and generating concise takeaways, saving time and boosting productivity. Designed for researchers and academics who need efficient document parsing, organizing, and metadata generation.

---

## Features

- **Google OAuth2 Authentication**: Enables secure and seamless login through Google accounts.
- **Google Drive Integration**: Stores research topics and articles in a structured folder system on Google Drive.
- **PDF Parsing and Management**: Automatically parses PDF files, extracting metadata and generating concise summaries.
- **AI-based Summarization**: Uses **BART** transformer models to generate summaries and key takeaways.
- **Multi-User Support**: Provides support for multiple users with individual accounts and folder structures.
- **MongoDB Storage**: User tokens and folder mappings are stored in MongoDB for scalable persistence.

---

## Prerequisites

- Python 3.10 or higher
- MongoDB running locally or in the cloud (MongoDB Atlas)
- Google Cloud project with OAuth2 credentials
- FastAPI for the backend
- React for the frontend (optional)

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Sanz009/ResearchAI.git
   cd ResearchAI` 

2.  Create a virtual environment and install dependencies:
    
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt` 
    
3.  Set up MongoDB:
    
    Ensure you have a running MongoDB instance either locally or in the cloud (e.g., MongoDB Atlas).
    
4.  Google OAuth Setup:
    
    -   Go to the Google Cloud Console.
    -   Set up OAuth2 credentials and add your redirect URI (typically `http://localhost:8000/oauth2callback`).
    -   Download your credentials file as `client_secret.json` and place it in the project root.
      
5.  Set environment variables:
    
    Create a `.env` file in the root directory with the following values:
    
    ```bash
    GOOGLE_CLIENT_ID=<your_google_client_id>
    GOOGLE_CLIENT_SECRET=<your_google_client_secret>
    MONGO_URI=<your_mongo_uri>
    FRONTEND_URL=http://localhost:3000
    BACKEND_URL=http://localhost:8000` 
    
6.  Run the backend server:
    
    ```bash
    uvicorn main:app --reload` 
    

---

## API Endpoints

### Authentication

-   **GET `/authorize`**: Redirects to Google OAuth2 for login.
-   **GET `/oauth2callback`**: Handles OAuth2 callback and saves tokens.

### Research Management

-   **GET `/fetch_topics`**: Retrieves research topics from the user’s Google Drive.
-   **POST `/upload_pdfs`**: Uploads PDFs to Google Drive under the user's folder.
-   **POST `/parse_pdfs`**: Parses PDFs and extracts metadata, summary, and key takeaways.
-   **POST `/update_entry`**: Updates existing research entries based on user input.
-   **DELETE `/delete_entry`**: Deletes a specific research entry.

---

## Project Structure

  ```bash
  ├── backend/
  │   ├── crypto_ops.py             # Handles encryption/decryption of user tokens
  │   ├── google_drive_helper.py    # Utility functions for Google Drive operations
  │   ├── mongo_db_ops.py           # Handles MongoDB token storage and folder mappings
  │   ├── main.py                   # Main FastAPI server logic
  ├── client_secret.json            # Google OAuth2 credentials file
  ├── .env                          # Environment variables file
  ├── requirements.txt              # Python package dependencies
  └── README.md                     # Project documentation (this file)
  ```

---

## Contribution

Feel free to fork this repository and submit pull requests with improvements or bug fixes. For major changes, please open an issue to discuss what you would like to change.

----------

## License

This project is licensed under the MIT License.
