import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import re
import io
import json
import random
import mimetypes
# Force correct mime-types for windows machines with corrupted registries
mimetypes.init()
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')

# pyrefly: ignore [missing-import]
import PyPDF2
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rag import analyze_report, ask_question
from dotenv import load_dotenv

from database import (
    init_db,
    register_user,
    verify_user_otp,
    authenticate_user,
    get_all_users,
    save_report,
    update_report_analysis,
    get_user_reports,
    get_all_reports,
    get_report_details,
    save_chat_message,
    get_chat_history,
    get_db_connection,
)
from email_utils import send_verification_email

load_dotenv(override=True)

app = FastAPI(title="AI Disease Prediction API")

EMAIL_REGEX = re.compile(r"^[\w\.\+-]+@[\w\.-]+\.\w+$")

def validate_email(email: str):
    if not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format. Only valid email addresses are allowed.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

# Models
class RegisterRequest(BaseModel):
    username: str  # Email address
    password: str
    role: str = "user"

class LoginRequest(BaseModel):
    username: str  # Email address or 'admin'
    password: str

class VerifyRequest(BaseModel):
    username: str  # Email address
    otp: str

class ChatRequest(BaseModel):
    report_id: int
    message: str

class ConfigUpdateRequest(BaseModel):
    groq_api_key: str = None
    smtp_email: str = None
    smtp_password: str = None
    smtp_host: str = None
    smtp_port: str = None

def check_admin_access(x_user_id: int):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized: User ID missing")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE id = ?", (x_user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or row["role"] != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin privileges required")

def get_user_role_from_db(user_id: int) -> str:
    if not user_id:
        return "user"
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row["role"] if row else "user"
    except Exception:
        return "user"

# Auth Routes
@app.post("/api/auth/register")
def register(request: RegisterRequest, background_tasks: BackgroundTasks):
    try:
        validate_email(request.username)
        # Generate 6-digit OTP
        otp = f"{random.randint(100000, 999999)}"
        
        # Only devaprakassh49@gmail.com is allowed to register as an admin, and is promoted automatically
        role = request.role
        if request.username == "devaprakassh49@gmail.com":
            role = "admin"
        elif role == "admin":
            role = "user"

        # Save user to database (always requires verification, is_verified=0)
        user = register_user(request.username, request.password, otp, role, is_verified=0)
        
        try:
            # Send verification email synchronously to provide instant validation feedback
            send_verification_email(request.username, otp)
        except Exception as mail_err:
            print(f"SMTP error on register: {mail_err}")
            # Roll back registration by deleting the unverified user record immediately
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = ?", (user["id"],))
                conn.commit()
                conn.close()
            except Exception as db_err:
                print(f"Failed to roll back user registration: {db_err}")
            raise HTTPException(
                status_code=500,
                detail=f"Registration failed: Failed to send verification email. Error: {str(mail_err)}"
            )
            
        resp = {
            "message": "Verification email sent",
            "email": request.username,
            "verification_required": True
        }
        return resp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/verify")
def verify(request: VerifyRequest):
    try:
        user = verify_user_otp(request.username, request.otp)
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/session")
def get_session(x_user_id: int = Header(None)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email as username, role, is_verified FROM users WHERE id = ?", (x_user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User session not found")
    return dict(row)

@app.post("/api/auth/login")
def login(request: LoginRequest, background_tasks: BackgroundTasks):
    validate_email(request.username)
    user = authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # If the account is already verified, bypass OTP verification entirely
    if user["is_verified"]:
        return {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "verification_required": False
        }
        
    # Generate 6-digit OTP for unverified registrations
    otp = f"{random.randint(100000, 999999)}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET otp = ? WHERE id = ?", (otp, user["id"]))
    conn.commit()
    conn.close()
    
    try:
        send_verification_email(user["username"], otp)
    except Exception as mail_err:
        print(f"SMTP error on login: {mail_err}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send verification email. Please check SMTP configuration. Error: {str(mail_err)}"
        )
        
    resp = {
        "message": "Verification email sent", 
        "email": user["username"],
        "verification_required": True
    }
    return resp



# Document Management & Predictions
@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...), 
    x_user_id: int = Header(None)
):
    if not file.filename.endswith(('.pdf', '.txt')):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are supported")
    
    user_id = x_user_id if x_user_id is not None else 1
    
    text = ""
    content = await file.read()
    
    try:
        if file.filename.endswith('.pdf'):
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        else:
            text = content.decode('utf-8')
            
        if not text.strip():
             raise ValueError("Extracted text is empty")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract text: {e}")
        
    try:
        report_id = save_report(user_id, file.filename, text)
        return {
            "message": "Document parsed and indexed successfully", 
            "report_id": report_id
        }
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to index report: {e}")

@app.get("/api/analyze")
def analyze(report_id: int):
    try:
        report = get_report_details(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Return cached analysis if available
        if report.get("analysis_json"):
            return {"analysis": json.loads(report["analysis_json"])}
            
        result = analyze_report(report["file_content"])
        
        # Save analysis to database
        update_report_analysis(report_id, json.dumps(result))
        return {"analysis": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reports")
def list_reports(
    x_user_id: int = Header(None), 
    x_user_role: str = Header(None)
):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    if x_user_role == "admin":
        reports = get_all_reports()
    else:
        reports = get_user_reports(x_user_id)
        
    return {"reports": reports}

@app.get("/api/reports/{report_id}")
def get_report(
    report_id: int, 
    x_user_id: int = Header(None), 
    x_user_role: str = Header(None)
):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    report = get_report_details(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    if x_user_role != "admin" and report["user_id"] != x_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
        
    analysis = json.loads(report["analysis_json"]) if report.get("analysis_json") else None
    chat_history = get_chat_history(report_id)
    
    return {
        "id": report["id"],
        "filename": report["filename"],
        "uploaded_at": report["uploaded_at"],
        "username": report["username"],
        "file_content": report["file_content"],
        "analysis": analysis,
        "chat_history": chat_history
    }

# Chat Route
@app.post("/api/chat")
def chat(request: ChatRequest):
    try:
        report = get_report_details(request.report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
            
        # Save user message to database
        save_chat_message(request.report_id, "user", request.message)
        
        # Get chat history (including the user message we just saved)
        history = get_chat_history(request.report_id)
        
        # Get AI response
        reply = ask_question(request.message, report["file_content"], chat_history=history)
        
        # Save bot reply to database
        save_chat_message(request.report_id, "bot", reply)
        
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Admin Routes
@app.get("/api/admin/users")
def list_users(x_user_id: int = Header(None)):
    check_admin_access(x_user_id)
    users = get_all_users()
    return {"users": users}

@app.get("/api/admin/config")
def get_config(x_user_id: int = Header(None)):
    check_admin_access(x_user_id)
    
    # Read dotenv variables
    load_dotenv(override=True)
    groq_api_key = os.getenv("GROQ_API_KEY") or ""
    smtp_email = os.getenv("SMTP_EMAIL") or ""
    smtp_password = os.getenv("SMTP_PASSWORD") or ""
    smtp_host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    smtp_port = os.getenv("SMTP_PORT") or "465"
    
    # Obfuscate values for security in response
    def obfuscate(val):
        if not val or val in ["your_gmail@gmail.com", "your_16_digit_google_app_password", "your_api_key_here"]:
            return ""
        if len(val) <= 6:
            return "******"
        return val[:3] + "******" + val[-3:]
        
    return {
        "groq_api_key": obfuscate(groq_api_key),
        "smtp_email": smtp_email,
        "smtp_password": obfuscate(smtp_password),
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "groq_api_key_configured": bool(groq_api_key and groq_api_key != "your_api_key_here"),
        "smtp_configured": bool(smtp_email and smtp_password and smtp_email != "your_gmail@gmail.com" and smtp_password != "your_16_digit_google_app_password")
    }

@app.post("/api/admin/config")
def update_config(request: ConfigUpdateRequest, x_user_id: int = Header(None)):
    check_admin_access(x_user_id)
        
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    
    # Read current lines
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
            
    # Parse existing values to recreate/update
    config_dict = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            parts = line.strip().split("=", 1)
            config_dict[parts[0].strip()] = parts[1].strip()
            
    # Update provided values (if not obfuscated placeholder)
    if request.groq_api_key and "******" not in request.groq_api_key:
        config_dict["GROQ_API_KEY"] = request.groq_api_key
    if request.smtp_email:
        config_dict["SMTP_EMAIL"] = request.smtp_email
    if request.smtp_password and "******" not in request.smtp_password:
        config_dict["SMTP_PASSWORD"] = request.smtp_password
    if request.smtp_host:
        config_dict["SMTP_HOST"] = request.smtp_host
    if request.smtp_port:
        config_dict["SMTP_PORT"] = request.smtp_port
        
    # Write back to .env file
    new_lines = []
    keys_written = set()
    
    # Preserve comments but update keys
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            parts = stripped.split("=", 1)
            k = parts[0].strip()
            if k in config_dict:
                new_lines.append(f"{k}={config_dict[k]}\n")
                keys_written.add(k)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    # Add any missing keys
    for k, v in config_dict.items():
        if k not in keys_written:
            new_lines.append(f"{k}={v}\n")
            
    with open(env_path, "w") as f:
        f.writelines(new_lines)
        
    # Force reload of environment
    load_dotenv(override=True)
    
    # Clear model name cache in rag.py
    import rag
    rag._best_model_name = None
    
    return {"message": "Configuration updated successfully"}

@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, x_user_id: int = Header(None)):
    check_admin_access(x_user_id)
    
    if user_id == x_user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, role FROM users WHERE id = ?", (user_id,))
    target = cursor.fetchone()
    
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    if target["role"] == "admin":
        conn.close()
        raise HTTPException(status_code=403, detail="Cannot delete another admin account")
    
    # CASCADE delete removes all reports and chat messages automatically
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": f"User {user_id} and all associated data deleted successfully"}

@app.get("/api/admin/mock-emails")
def get_mock_emails(x_user_id: int = Header(None)):
    check_admin_access(x_user_id)
        
    log_path = os.path.join(os.path.dirname(__file__), "mock_emails.txt")
    if not os.path.exists(log_path):
        return {"emails": []}
        
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        # Parse into a list of structures or just return lines
        emails = []
        for line in reversed(lines): # Show newest first
            line = line.strip()
            if not line:
                continue
            # Format: [timestamp] To: email | OTP: otp
            match = re.match(r"\[(.*?)\] To: (.*?) \| OTP: (.*)", line)
            if match:
                emails.append({
                    "timestamp": match.group(1),
                    "to": match.group(2),
                    "otp": match.group(3)
                })
            else:
                emails.append({"raw": line})
        return {"emails": emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read mock logs: {e}")

# Mount frontend directory
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if not os.path.exists(frontend_dir):
    os.makedirs(frontend_dir)
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
