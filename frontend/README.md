# Research AI

The Research AI is a web application designed to interact with the Research AI backend running on python. It provides a user-friendly interface for managing research topics, uploading and parsing PDFs, and accessing data from Google Drive.

## Table of Contents

1. [Features](#features)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Contributing](#contributing)
6. [License](#license)

## Features

- User authentication via Google OAuth2
- Manage research topics
- Upload and parse PDFs
- View and edit existing data
- Fetch data from Google Drive

## Installation

### Prerequisites

Ensure you have the following installed:
- Node.js (version 14 or later)
- npm (or yarn)

### Clone the Repository

Clone the frontend repository to your local machine:

```bash
git clone https://github.com/Sanz009/ResearchAI.git
cd ResearchAI/frontend
```

### Install Dependencies

Navigate to the frontend directory and install the required dependencies:

```bash
npm install
# or
yarn install` 
```

## Configuration

### Environment Variables

Create a `.env` file in the root of the frontend directory and add the following environment variables:

env

```bash
REACT_APP_BACKEND_URL=http://localhost:8000
REACT_APP_GOOGLE_CLIENT_ID=your_google_client_id` 
```

Replace `your_google_client_id` with your actual Google Client ID. The `REACT_APP_BACKEND_URL` should point to your backend service.

### Running the Application

To start the development server, run:

```bash
npm start
# or
yarn start` 
```

The application will be available at `http://localhost:3000`.

### Building for Production

To create a production build, run:

```bash
npm run build
# or
yarn build` 
```

The production build will be available in the `build` directory.

## Usage

1.  **Authenticate**: Users will be redirected to Google OAuth2 for authentication.
2.  **Manage Topics**: View, add, and delete research topics.
3.  **Upload PDFs**: Upload PDF files for parsing and extracting data.
4.  **View Data**: Access and manage data from Google Drive.

## Contributing

Contributions are welcome! Please follow these steps to contribute:

1.  Fork the repository.
2.  Create a new branch for your changes.
3.  Make your changes and test them.
4.  Submit a pull request with a detailed description of your changes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.