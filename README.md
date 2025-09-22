# AI Chatbot Platform

A minimal Chatbot Platform built with **FastAPI** (backend) and **HTML/CSS/JS** (frontend).  
It supports authentication, project/agent creation, document uploads, and context-aware conversations with an LLM using the OpenAI Responses API.

---

## Live Demo

You can try the hosted version here:  
[https://chatbot-4-jvnz.onrender.com/](https://chatbot-4-jvnz.onrender.com/)

---

## Features

### Authentication
- Register and log in with email and password
- JWT-based authentication
- Secure password hashing with `bcrypt`

### Projects / Agents
- Each user can create multiple projects
- Projects are private to each user
- Projects store uploaded files and chat history

### Document Upload
- Supports `.pdf`, `.docx`, and `.txt` files
- Extracts text and uses it as context during chats
- Optional support for uploading to the OpenAI Files API

### Chat
- Chat sessions are scoped to a project
- Uploaded documents are used as context when generating answers
- Integrated with the OpenAI Responses API (extensible to other LLM services)

### Frontend
- Simple login/registration form (email + password)
- Project creation and selection
- File upload and chat box with conversation history

---

## Project Structure

```
WEB_CHATBOT/
 ├── backend/
 │    ├── main.py          # FastAPI application
 │    ├── index.html       # Frontend UI
 │    ├── requirements.txt # Dependencies
 │    ├── .env.example     # Example environment variables
 │    └── uploads/         # Temporary file storage (ignored in git)
 ├── README.md             # Project documentation
 └── .gitignore            # Ignore venv, .env, cache files, etc.
```

---

## Setup and Installation

### Prerequisites
- Python 3.9+
- An [OpenAI API key](https://platform.openai.com/) (or compatible provider)
- Git

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR-USERNAME/web-chatbot.git
   cd web-chatbot/backend
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and set your secrets:
   ```
   OPENAI_API_KEY=your_openai_api_key
   OPENAI_MODEL=gpt-4o-mini
   SECRET_KEY=your_secret_key
   ```

5. Run the application:
   ```bash
   uvicorn main:app --reload
   ```

6. Open the app in your browser:
   ```
   http://127.0.0.1:8000/
   ```

---

## Deployment

This project is deployed on **Render**.  
To deploy your own version:
1. Push your code to GitHub
2. Create a new **Web Service** on [Render](https://render.com/)
3. Connect your GitHub repo
4. Set build command:
   ```bash
   pip install -r backend/requirements.txt
   ```
5. Set start command:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 10000
   ```
6. Add environment variables in the Render dashboard (`OPENAI_API_KEY`, `OPENAI_MODEL`, `SECRET_KEY`)

Your app will be live at a Render-provided URL.

---
