# ResearchAI

## Overview

**ResearchAI** is a powerful AI-driven research management tool that simplifies managing, summarizing, and organizing research papers. It integrates with **Google Drive**, providing seamless authentication using **Google OAuth2** and storage for research topics and articles. ResearchAI uses **FastAPI** for a robust backend with AI models such as **BART** for summarization. Built to serve researchers, scholars, and academics, it assists in parsing PDFs and generating concise takeaways, saving time and boosting productivity.

---

## Features

- **Google OAuth2 Authentication**: Secure login using your Google account.
- **Google Drive Integration**: Store research data and organize articles directly into your Google Drive.
- **PDF Parsing & Management**: Upload, parse, and manage your PDFs with ease.
- **Summarization**: Generate quick summaries and key takeaways using BART (pre-trained model).
- **MongoDB Storage**: Store user tokens, research topics, and metadata efficiently.
- **Multi-user support**: Ensures seamless handling of multiple user sessions.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- MongoDB (running locally or in the cloud)
- Google Cloud Project with OAuth2 credentials
- FastAPI for backend API
- React for frontend interface
