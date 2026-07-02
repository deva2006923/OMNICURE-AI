import os
import sqlite3
import hashlib
from datetime import datetime

if os.getenv("VERCEL") == "1":
    DB_PATH = "/tmp/disease_prediction.db"
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "disease_prediction.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), 100000)
    return dk.hex(), salt

def init_db():
    # Automated reset for old database schemas (missing email column)
    if os.path.exists(DB_PATH):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users)")
            columns = [row["name"] for row in cursor.fetchall()]
            conn.close()
            if columns and "email" not in columns:
                print("Old database schema detected. Resetting database...")
                os.remove(DB_PATH)
        except Exception as e:
            print("Error checking schema, resetting DB file:", e)
            try:
                os.remove(DB_PATH)
            except Exception:
                pass

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table with verification and email columns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            otp TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    
    # Create reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            file_content TEXT NOT NULL,
            analysis_json TEXT,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """)
    
    # Create chat_messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE
        )
    """)
    
    # Clean up legacy admin account if present
    cursor.execute("DELETE FROM users WHERE email = 'admin@omnicure.com'")
    
    conn.commit()
    conn.close()

# User CRUD
def register_user(email: str, password: str, otp: str = None, role: str = 'user', is_verified: int = 0) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check duplicate
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    if user:
        if user["is_verified"] == 1:
            conn.close()
            raise Exception("Email already registered")
        else:
            # If the user exists but is not verified, delete them so they can register fresh
            cursor.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        
    pwd_hash, salt = hash_password(password)
    now = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO users (email, password_hash, salt, role, otp, is_verified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, pwd_hash, salt, role, otp, is_verified, now)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": user_id, "username": email, "role": role, "is_verified": is_verified}


def verify_user_otp(email: str, otp: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise Exception("Account not found")
        
    if user["is_verified"] == 1:
        conn.close()
        return {"id": user["id"], "username": user["email"], "role": user["role"]}
        
    if user["otp"] == otp:
        cursor.execute("UPDATE users SET is_verified = 1, otp = NULL WHERE id = ?", (user["id"],))
        conn.commit()
        user_id = user["id"]
        role = user["role"]
        conn.close()
        return {"id": user_id, "username": email, "role": role}
    else:
        conn.close()
        raise Exception("Invalid verification code")

def authenticate_user(email: str, password: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return None
        
    db_hash = user["password_hash"]
    salt = user["salt"]
    
    test_hash, _ = hash_password(password, salt)
    if test_hash == db_hash:
        return {
            "id": user["id"],
            "username": user["email"],
            "role": user["role"],
            "is_verified": int(user["is_verified"])
        }
    return None

def get_all_users() -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Return email as username for interface compatibility
    cursor.execute("""
        SELECT u.id, u.email as username, u.role, u.created_at, COUNT(r.id) as report_count
        FROM users u
        LEFT JOIN reports r ON u.id = r.user_id
        GROUP BY u.id
    """)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

# Reports CRUD
def save_report(user_id: int, filename: str, file_content: str, analysis_json: str = None) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO reports (user_id, filename, file_content, analysis_json, uploaded_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, filename, file_content, analysis_json, now)
    )
    report_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return report_id

def update_report_analysis(report_id: int, analysis_json: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reports SET analysis_json = ? WHERE id = ?", (analysis_json, report_id))
    conn.commit()
    conn.close()

def get_user_reports(user_id: int) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, filename, uploaded_at FROM reports WHERE user_id = ? ORDER BY uploaded_at DESC", (user_id,))
    reports = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reports

def get_all_reports() -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.id, r.user_id, r.filename, r.uploaded_at, u.email as username 
        FROM reports r
        JOIN users u ON r.user_id = u.id
        ORDER BY r.uploaded_at DESC
    """)
    reports = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reports

def get_report_details(report_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT r.id, r.user_id, r.filename, r.file_content, r.analysis_json, r.uploaded_at, u.email as username 
        FROM reports r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
    """, (report_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    return dict(row)

# Chat CRUD
def save_chat_message(report_id: int, sender: str, message: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO chat_messages (report_id, sender, message, timestamp) VALUES (?, ?, ?, ?)",
        (report_id, sender, message, now)
    )
    conn.commit()
    conn.close()

def get_chat_history(report_id: int) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT sender, message, timestamp FROM chat_messages WHERE report_id = ? ORDER BY id ASC", (report_id,))
    chat = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return chat
