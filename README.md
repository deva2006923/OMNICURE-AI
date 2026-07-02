# OmniCure AI - Clinical Report Intelligence & Disease Prediction Suite

OmniCure AI is an enterprise-grade clinical assistant and laboratory report analysis suite. The application parses health reports (PDF/TXT), analyzes them using local rules combined with a Retrieval-Augmented Generation (RAG) pipeline powered by the Groq LLM, and provides a multi-turn conversational interface with session history memory.

---

## Key Features

1. **Secure 2FA OTP Authentication (SMTP)**
   * Every login and signup is secured with a 6-digit verification code sent via Gmail SMTP.
   * **Registration Rollback**: If the verification email fails to transmit (SMTP credential errors or network drops), the database automatically rolls back and deletes the unverified registration to prevent locked/orphaned user accounts.
   * **Re-registration Bypass**: Users with unverified accounts can register again to clear out stale database logs and receive a new code.
   
2. **Clinical Document Analyzer**
   * Parses text files and PDF sheets (using `PyPDF2`).
   * Extracts vital health metrics (Fasting Blood Glucose, HbA1c, Cholesterol, LDL, HDL, Blood Pressure, etc.).
   * Flags and displays abnormalities against standard diagnostic reference ranges in a sleek, non-clipped card container.

3. **AI Disease Risk Predictions**
   * Automatically calculates clinical risk levels (Low, Medium, High Risk) for chronic diseases such as Diabetes, Hypertension, and Cardiovascular conditions.
   * Explains diagnostic reasonings directly on the dashboard.

4. **Multi-Turn Conversational RAG Bot**
   * Chat with "OmniCure AI" about your specific report details.
   * Keeps track of database-persisted chat history enabling true context-aware follow-up questions (e.g., asking *"Is that high?"* after querying blood sugar).
   * Formats responses cleanly with bullet points and automatically appends medical safety disclaimers.

5. **Admin Integrations Panel**
   * Visible only to authorized Administrators.
   * Allows live configuration of API keys (Groq API, Gmail App Passwords) and monitors server status, active users list, and mail logs.

---

## Technology Stack

* **Backend**: FastAPI (Python 3.12+), SQLite (Enforced foreign keys for relational integrity), `python-dotenv` for configuration, `groq` SDK for RAG, and `smtplib` for transaction mail delivery.
* **Frontend**: HTML5, Vanilla CSS (Premium Dark Mode, Glassmorphic effects, Custom arrow-free scrollbars), Vanilla JavaScript (Router, DOM bindings, upload progress, interactive chat).

---

## Directory Structure

```
disease-predicting-system/
├── backend/
│   ├── main.py                     # FastAPI server, endpoints, and server config
│   ├── database.py                 # SQLite database schema, user records, and CRUD operations
│   ├── rag.py                      # Groq RAG pipelines, text parser, and prompt builder
│   ├── email_utils.py              # Gmail SMTP setup and OTP delivery logic
│   ├── .env.example                # Sample environment template (safe for Git)
│   └── disease_prediction.db       # SQLite Database storage
├── frontend/
│   ├── index.html                  # Single Page Application view markup
│   ├── style.css                   # Glassmorphic dark styling & custom scrollbars
│   └── app.js                      # SPA state machine, chat handler, and API bindings
├── README.md                       # Comprehensive repository documentation
└── sample_report.txt               # Sample laboratory text report for evaluation
```

---

## Installation & Setup

### 1. Clone & Initialize Environment
Activate a Python virtual environment in the project directory:

```bash
# Windows
python -m venv backend/venv
backend/venv/Scripts/activate

# Linux / MacOS
python3 -m venv backend/venv
source backend/venv/bin/activate
```

### 2. Install Dependencies
Install all required packages:

```bash
pip install fastapi uvicorn pydantic python-dotenv groq PyPDF2
```

### 3. Environment Configuration
Copy the sample environment file in the `backend/` directory:

```bash
cp backend/.env.example backend/.env
```

Open the newly created `backend/.env` file and fill in your details:
* **`GROQ_API_KEY`**: Retrieve a free key from the [Groq Console](https://console.groq.com/keys).
* **`SMTP_EMAIL`**: Your admin Gmail address (e.g. `yourname@gmail.com`).
* **`SMTP_PASSWORD`**: A 16-character App Password generated via Google Accounts -> Security -> App Passwords.

---

## Running the Application

1. **Start the Backend Server**:
   Ensure you are in the workspace root directory and run:
   ```bash
   backend/venv/Scripts/python backend/main.py
   ```
   *The server runs locally at `http://127.0.0.1:8080` and automatically hosts the static frontend page.*

2. **Access the Interface**:
   Open your browser and navigate to **`http://localhost:8080`**.

3. **Register & Log in as Admin**:
   * Register using your designated **admin email address** on the Sign Up page.
   * A 6-digit OTP code will be sent to your inbox — use it to verify and activate your account.
   * The owner's email (`devaprakassh49@gmail.com`) is automatically promoted to `admin` role upon registration.
   * All subsequent logins also require OTP verification if the account is not yet verified.

---

## Medical Disclaimer

*OmniCure AI is an educational diagnostic tool. It is not intended to substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of a physician or other qualified health provider with any questions you may have regarding a medical condition.*
