# main.py
import os
import uuid
import tempfile
import json
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

# Auth/security
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

# PDF/DOCX parsing
import PyPDF2
import docx

# For serving frontend
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_FILES_URL = "https://api.openai.com/v1/files"

app = FastAPI(title="LLM Chat + Doc Upload + Auth")

# ---------------- Security Setup ----------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")  # replace for production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# In-memory stores
users_db = {}  # {email: {"email":..., "hashed_pw":...}}
PROJECTS = {}  # project_id -> {"name":..., "owner":..., "files": [...], "prompts": [...]}

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_password(plain_pw, hashed_pw):
    return pwd_context.verify(plain_pw, hashed_pw)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_current_user(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

# ---------------- Auth Endpoints ----------------
@app.post("/register")
async def register(email: str = Form(...), password: str = Form(...)):
    if email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    users_db[email] = {"email": email, "hashed_pw": get_password_hash(password)}
    return {"msg": "User registered successfully"}

@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    user = users_db.get(email)
    if not user or not verify_password(password, user["hashed_pw"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    token = create_access_token({"sub": email})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
async def me(token: str):
    email = get_current_user(token)
    return {"email": email}

# ---------------- Project Management ----------------
@app.post("/projects/create")
async def create_project(name: str = Form(...), token: str = Form(...)):
    email = get_current_user(token)
    project_id = str(uuid.uuid4())
    PROJECTS[project_id] = {"name": name, "owner": email, "files": [], "prompts": []}
    return {"project_id": project_id, "name": name}

@app.get("/projects/list")
async def list_projects(token: str):
    email = get_current_user(token)
    projects = [
        {"id": pid, "name": p["name"]}
        for pid, p in PROJECTS.items()
        if p["owner"] == email
    ]
    return {"projects": projects}

# ---------------- File Extraction ----------------
def extract_text_from_pdf(path: str) -> str:
    text_parts = []
    try:
        reader = PyPDF2.PdfReader(path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    except Exception:
        pass
    return "\n".join(text_parts)

def extract_text_from_docx(path: str) -> str:
    try:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs if p.text])
    except Exception:
        return ""

def extract_text_from_file(path: str, filename: str) -> str:
    if filename.lower().endswith(".pdf"):
        return extract_text_from_pdf(path)
    if filename.lower().endswith(".docx"):
        return extract_text_from_docx(path)
    try:
        with open(path, "rb") as f:
            raw = f.read()
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""

# ---------------- Upload ----------------
@app.post("/upload")
async def upload_file(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    token: str = Form(...)
):
    email = get_current_user(token)
    project = PROJECTS.get(project_id)
    if not project or project["owner"] != email:
        raise HTTPException(status_code=403, detail="Unauthorized or project not found")

    suffix = os.path.splitext(file.filename)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    contents = await file.read()
    tmp.write(contents)
    tmp.flush()
    tmp.close()

    extracted_text = extract_text_from_file(tmp.name, file.filename)

    file_id = str(uuid.uuid4())
    file_record = {
        "id": file_id,
        "name": file.filename,
        "text": extracted_text,
        "uploaded_by": email,
    }
    project["files"].append(file_record)

    return {
        "project_id": project_id,
        "file_id": file_id,
        "filename": file.filename,
        "text_snippet": extracted_text[:400],
        "uploaded_by": email
    }

# Optional: Upload to OpenAI Files API
@app.post("/upload_to_openai")
async def upload_to_openai(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    token: str = Form(...)
):
    email = get_current_user(token)
    project = PROJECTS.get(project_id)
    if not project or project["owner"] != email:
        raise HTTPException(status_code=403, detail="Unauthorized or project not found")

    headers = {"Authorization": f"Bearer {OPENAI_KEY}"}
    fd = {"purpose": "answers"}
    files = {"file": (file.filename, await file.read())}

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(OPENAI_FILES_URL, headers=headers, data=fd, files=files)

    if r.status_code != 200:
        return {"error": "OpenAI API error", "detail": r.text}

    resp = r.json()
    project["files"].append({
        "id": resp.get("id"),
        "name": file.filename,
        "text": "",
        "uploaded_by": email,
        "openai_file_id": resp.get("id")
    })
    return resp

# ---------------- Chat ----------------
class ChatRequest(BaseModel):
    project_id: str
    prompt: str
    temperature: Optional[float] = 0.0
    token: str

def build_context_text(project_id: str):
    project = PROJECTS.get(project_id, {})
    files = project.get("files", [])
    pieces = []
    total_limit = 3000
    for f in files:
        snippet = (f.get("text") or "")[:1500]
        if snippet:
            pieces.append(f"--- Document: {f.get('name')} ---\n{snippet}\n")
    return "\n".join(pieces)[:total_limit]

@app.post("/chat")
async def chat(req: ChatRequest):
    email = get_current_user(req.token)
    project = PROJECTS.get(req.project_id)
    if not project or project["owner"] != email:
        raise HTTPException(status_code=403, detail="Unauthorized or project not found")

    context_text = build_context_text(req.project_id)
    system_prefix = ""
    if context_text:
        system_prefix = (
            "You are a helpful assistant. Use the following document(s) to answer the user's question. "
            "If the document doesn't contain the answer, say so.\n\n"
            f"{context_text}\n\n"
        )

    final_input = system_prefix + "User question:\n" + req.prompt

    headers = {"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"}
    body = {"model": OPENAI_MODEL, "input": final_input}

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(OPENAI_RESPONSES_URL, headers=headers, json=body)
    if r.status_code != 200:
        return {"error": "OpenAI API error", "status": r.status_code, "detail": r.text}

    resp = r.json()
    answer_text = ""

    if isinstance(resp, dict) and "output_text" in resp:
        answer_text = resp["output_text"]
    elif isinstance(resp, dict) and "output" in resp:
        outputs = resp.get("output", [])
        texts = []
        for item in outputs:
            content = item.get("content") or []
            if isinstance(content, list):
                for c in content:
                    text = c.get("text") if isinstance(c, dict) else None
                    if text:
                        texts.append(text)
            else:
                t = item.get("text")
                if t:
                    texts.append(t)
        answer_text = "\n".join(texts).strip()
    else:
        answer_text = json.dumps(resp)[:1000]

    project["prompts"].append(
        {"prompt": req.prompt, "answer": answer_text, "user": email}
    )

    return {"reply": answer_text, "user": email}
