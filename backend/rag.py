import os
import re
import json
from groq import Groq
from dotenv import load_dotenv
from database import get_system_config

global_document_text = ""
_best_model_name = None

# Ordered preference list — verified active Groq models (July 2026)
# Only fast, reliable models that support chat completions
MODEL_PREFERENCES = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "llama3-70b-8192",
    "gemma2-9b-it",
    "llama-3.3-70b-versatile",
]

def load_rag_dotenv():
    """Load environment variables using absolute path of backend/.env."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv(override=True)

def _has_valid_api_key() -> bool:
    load_rag_dotenv()
    key = get_system_config("GROQ_API_KEY", "") or ""
    is_valid = bool(key.strip() and key.strip() not in ("your_api_key_here", "dummy_key", ""))
    print(f"[RAG] _has_valid_api_key check: exists={bool(key.strip())}, length={len(key.strip())}, is_valid={is_valid}")
    return is_valid

def get_groq_client():
    """Create a Groq client using the configured API key."""
    api_key = get_system_config("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "")
    return Groq(api_key=api_key.strip())

def get_best_model_name() -> str:
    """Return the best available Groq model. Result is cached per process."""
    global _best_model_name
    if _best_model_name:
        return _best_model_name

    if not _has_valid_api_key():
        _best_model_name = MODEL_PREFERENCES[0]
        return _best_model_name

    try:
        client = get_groq_client()
        available = {m.id for m in client.models.list().data}
        print(f"[RAG] Available Groq models: {sorted(available)}")
        for pref in MODEL_PREFERENCES:
            if pref in available:
                _best_model_name = pref
                print(f"[RAG] Selected model: {_best_model_name}")
                return _best_model_name
        # Fallback: pick any available text model
        text_models = sorted([
            m for m in available
            if any(x in m.lower() for x in ["llama", "gemma", "mixtral", "qwen", "mistral"])
        ])
        if text_models:
            _best_model_name = text_models[0]
            print(f"[RAG] Fallback model selected: {_best_model_name}")
            return _best_model_name
    except Exception as e:
        print(f"[RAG] Could not list models, defaulting: {e}")

    _best_model_name = MODEL_PREFERENCES[0]
    return _best_model_name


def _safe_content(response) -> str:
    """Safely extract text content from a Groq response, handling None gracefully."""
    try:
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except (AttributeError, IndexError, TypeError) as e:
        import traceback
        print("[RAG] Error extracting content shape inside _safe_content:")
        traceback.print_exc()
        return ""


def _strip_markdown_json(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from model output."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```\s*$', '', text)
    return text.strip()


def _call_groq(messages: list, max_tokens: int = 1024, temperature: float = 0.3) -> str:
    """
    Central Groq API caller with robust error handling.
    Tries max_tokens first, falls back to max_completion_tokens for older SDK versions.
    Returns the text content or raises an exception.
    """
    import traceback
    client = get_groq_client()
    model_name = get_best_model_name()

    # Try the call — handle both old and new SDK parameter naming
    kwargs = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    last_error = None
    # Try with max_tokens first (works on most groq SDK versions)
    for token_param in ("max_tokens", "max_completion_tokens"):
        try:
            print(f"[RAG] Invoking Groq model '{model_name}' using parameter '{token_param}'...")
            response = client.chat.completions.create(**kwargs, **{token_param: max_tokens})
            content = _safe_content(response)
            if content:
                print(f"[RAG] Got response from {model_name} using {token_param}")
                return content
            else:
                print(f"[RAG] Received empty/invalid content structure using {token_param}")
        except TypeError as e:
            last_error = e
            print(f"[RAG] TypeError with {token_param} parameter: {e} — trying next fallback.")
            traceback.print_exc()
            continue
        except Exception as e:
            last_error = e
            print(f"[RAG] General Groq API error with {token_param}: {e}")
            traceback.print_exc()
            break

    raise last_error or Exception("Groq returned empty content")


# ---------------------------------------------------------------------------
# Rule-based fallback analyser (runs when Groq is unavailable)
# ---------------------------------------------------------------------------
def analyze_report_mock(text: str) -> dict:
    metrics = []
    abnormalities = []
    predictions = []

    # 1. Blood Pressure
    bp = re.search(r'(?:Blood Pressure|BP)[:\s]+(\d+/\d+)\s*mmHg', text, re.IGNORECASE)
    if bp:
        val = bp.group(1)
        metrics.append({"name": "Blood Pressure", "value": val + " mmHg"})
        try:
            sys_val, dia_val = map(int, val.split('/'))
            if sys_val >= 140 or dia_val >= 90:
                abnormalities.append(f"High Blood Pressure ({val} mmHg)")
                predictions.append({
                    "disease": "Hypertension (High Blood Pressure)",
                    "risk_level": "High",
                    "reason": f"Systolic ≥ 140 or diastolic ≥ 90 mmHg (found {val} mmHg)."
                })
            elif sys_val >= 130 or dia_val >= 80:
                abnormalities.append(f"Elevated Blood Pressure ({val} mmHg)")
                predictions.append({
                    "disease": "Hypertension (High Blood Pressure)",
                    "risk_level": "Medium",
                    "reason": f"Elevated BP measurements (found {val} mmHg)."
                })
        except Exception:
            pass

    # 2. Fasting Blood Glucose
    glc = re.search(r'(?:Fasting Blood Glucose|Glucose)[:\s]+(\d+(?:\.\d+)?)\s*mg/dL', text, re.IGNORECASE)
    if glc:
        val = float(glc.group(1))
        metrics.append({"name": "Fasting Blood Glucose", "value": f"{val} mg/dL"})
        if val >= 126:
            abnormalities.append(f"High Fasting Blood Glucose ({val} mg/dL)")
            predictions.append({
                "disease": "Diabetes Mellitus (Type 2)",
                "risk_level": "High",
                "reason": f"Fasting Blood Glucose ≥ 126 mg/dL (found {val} mg/dL)."
            })
        elif val >= 100:
            abnormalities.append(f"Impaired Fasting Glucose ({val} mg/dL)")
            predictions.append({
                "disease": "Diabetes Mellitus (Type 2)",
                "risk_level": "Medium",
                "reason": f"Fasting Blood Glucose in prediabetes range (found {val} mg/dL)."
            })

    # 3. HbA1c
    hba = re.search(r'HbA1c[:\s]+(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    if hba:
        val = float(hba.group(1))
        metrics.append({"name": "HbA1c", "value": f"{val}%"})
        if val >= 6.5:
            abnormalities.append(f"Elevated HbA1c ({val}%)")
            found = next((p for p in predictions if "Diabetes" in p["disease"]), None)
            if found:
                found["risk_level"] = "High"
                found["reason"] += f" HbA1c also high ({val}%)."
            else:
                predictions.append({"disease": "Diabetes Mellitus (Type 2)", "risk_level": "High",
                                     "reason": f"HbA1c ≥ 6.5% (found {val}%)."})
        elif val >= 5.7:
            abnormalities.append(f"Borderline HbA1c ({val}%)")

    # 4. Total Cholesterol
    chol = re.search(r'(?:Total Cholesterol|Cholesterol)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if chol:
        val = int(chol.group(1))
        metrics.append({"name": "Total Cholesterol", "value": f"{val} mg/dL"})
        if val >= 240:
            abnormalities.append(f"High Total Cholesterol ({val} mg/dL)")
            predictions.append({"disease": "Hyperlipidemia / Cardiovascular Disease", "risk_level": "High",
                                 "reason": f"Total cholesterol ≥ 240 mg/dL (found {val} mg/dL)."})
        elif val >= 200:
            abnormalities.append(f"Borderline High Cholesterol ({val} mg/dL)")
            predictions.append({"disease": "Hyperlipidemia / Cardiovascular Disease", "risk_level": "Medium",
                                 "reason": f"Total cholesterol elevated (found {val} mg/dL)."})

    # 5. LDL Cholesterol
    ldl = re.search(r'(?:LDL Cholesterol|LDL)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if ldl:
        val = int(ldl.group(1))
        metrics.append({"name": "LDL Cholesterol", "value": f"{val} mg/dL"})
        if val >= 160:
            abnormalities.append(f"High LDL Cholesterol ({val} mg/dL)")
            found = next((p for p in predictions if "Cardiovascular" in p["disease"]), None)
            if found:
                found["risk_level"] = "High"
                found["reason"] += f" LDL also high ({val} mg/dL)."
            else:
                predictions.append({"disease": "Hyperlipidemia / Cardiovascular Disease", "risk_level": "High",
                                     "reason": f"LDL ≥ 160 mg/dL (found {val} mg/dL)."})
        elif val >= 130:
            abnormalities.append(f"Borderline High LDL ({val} mg/dL)")

    # 6. HDL Cholesterol
    hdl = re.search(r'(?:HDL Cholesterol|HDL)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if hdl:
        val = int(hdl.group(1))
        metrics.append({"name": "HDL Cholesterol", "value": f"{val} mg/dL"})
        if val < 40:
            abnormalities.append(f"Low HDL Cholesterol ({val} mg/dL — protective factor reduced)")

    # 7. Triglycerides
    tg = re.search(r'(?:Triglycerides|TG)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if tg:
        val = int(tg.group(1))
        metrics.append({"name": "Triglycerides", "value": f"{val} mg/dL"})
        if val >= 200:
            abnormalities.append(f"High Triglycerides ({val} mg/dL)")
        elif val >= 150:
            abnormalities.append(f"Borderline High Triglycerides ({val} mg/dL)")

    # 8. BMI
    bmi = re.search(r'BMI[:\s]+(\d+(?:\.\d+)?)\s*(?:kg/m2)?', text, re.IGNORECASE)
    if bmi:
        val = float(bmi.group(1))
        metrics.append({"name": "BMI", "value": f"{val} kg/m²"})
        if val >= 30:
            abnormalities.append(f"High BMI ({val} kg/m² — Obese)")
            predictions.append({"disease": "Obesity & Metabolic Syndrome", "risk_level": "High",
                                 "reason": f"BMI ≥ 30 (found {val} kg/m²)."})
        elif val >= 25:
            abnormalities.append(f"Overweight BMI ({val} kg/m²)")
            predictions.append({"disease": "Obesity & Metabolic Syndrome", "risk_level": "Medium",
                                 "reason": f"BMI in overweight range (found {val} kg/m²)."})

    # 9. Heart Rate
    hr = re.search(r'(?:Heart Rate|HR|Pulse)[:\s]+(\d+)\s*bpm', text, re.IGNORECASE)
    if hr:
        val = int(hr.group(1))
        metrics.append({"name": "Heart Rate", "value": f"{val} bpm"})
        if val > 100:
            abnormalities.append(f"Elevated Heart Rate ({val} bpm — Tachycardia)")
        elif val < 60:
            abnormalities.append(f"Low Heart Rate ({val} bpm — Bradycardia)")

    # Generic fallback
    if not metrics:
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('-') and ':' in line:
                parts = line[1:].split(':', 1)
                metrics.append({"name": parts[0].strip(), "value": parts[1].strip()})

    if not predictions:
        predictions.append({
            "disease": "General Health Review",
            "risk_level": "Low",
            "reason": "No major abnormal vital signs or laboratory values were extracted from this report."
        })

    return {
        "metrics": metrics,
        "abnormalities": abnormalities,
        "predictions": predictions,
        "demo_mode": True
    }


# ---------------------------------------------------------------------------
# Groq-powered report analysis
# ---------------------------------------------------------------------------
def analyze_report(custom_text: str = None) -> dict:
    load_rag_dotenv()
    text = custom_text if custom_text is not None else global_document_text
    if not text:
        raise Exception("No document text provided")

    if not _has_valid_api_key():
        print("[RAG] No valid GROQ_API_KEY — using rule-based analyser")
        return analyze_report_mock(text)

    prompt = f"""You are a clinical diagnostic AI. Analyze the following patient medical report.

REPORT:
{text}

Tasks:
1. Extract all key lab metrics and vital signs mentioned.
2. Identify any values outside normal clinical reference ranges and list them as abnormalities.
3. Predict potential diseases or health conditions (e.g., Diabetes, Hypertension, Cardiovascular Disease) with a risk level (Low / Medium / High) and brief clinical reasoning.

Return ONLY a valid JSON object — no markdown, no code fences, no explanation outside the JSON. Schema:
{{
  "metrics": [{{"name": "string", "value": "string"}}],
  "abnormalities": ["string"],
  "predictions": [{{"disease": "string", "risk_level": "Low|Medium|High", "reason": "string"}}]
}}"""

    try:
        result_text = _call_groq(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.2,
        )
        result_text = _strip_markdown_json(result_text)
        print(f"[RAG] analyze_report raw response: {result_text[:120]}...")

        try:
            parsed = json.loads(result_text)
            if "metrics" in parsed and "predictions" in parsed:
                return parsed
            raise ValueError("Missing expected keys in JSON")
        except (json.JSONDecodeError, ValueError) as parse_err:
            import traceback
            print(f"[RAG] JSON parse error: {parse_err} — falling back to rule-based")
            traceback.print_exc()
            return analyze_report_mock(text)

    except Exception as e:
        import traceback
        print(f"[RAG] Groq API error in analyze_report: {e} — falling back to rule-based")
        traceback.print_exc()
        return analyze_report_mock(text)


# ---------------------------------------------------------------------------
# Groq-powered conversational RAG chat
# ---------------------------------------------------------------------------
def ask_question(question: str, custom_text: str = None, chat_history: list = None) -> str:
    load_rag_dotenv()
    text = custom_text if custom_text is not None else global_document_text
    if not text:
        raise Exception("No document text available for this report")

    if not _has_valid_api_key():
        return (
            "⚠️ **AI Chat Unavailable** — No Groq API Key is configured on this server. "
            "The rule-based report analysis above is still available. "
            "To enable live AI chat, add your `GROQ_API_KEY` in the Vercel environment variables."
        )

    system_prompt = (
        "You are OmniCure AI, a professional and compassionate medical report assistant. "
        "Answer questions based strictly on the patient report provided. "
        "Be concise, accurate, and structured. Use bullet points where helpful. "
        "Always end your response with a one-line medical disclaimer."
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Inject the full report as context
    messages.append({
        "role": "user",
        "content": f"Here is the patient medical report:\n\n{text}\n\nPlease use this to answer my questions."
    })
    messages.append({
        "role": "assistant",
        "content": "Understood. I have reviewed the report and am ready to answer your clinical questions."
    })

    # Replay prior chat history (skip last item — that's the current question)
    if chat_history:
        for msg in chat_history[:-1]:
            role = "user" if msg["sender"] == "user" else "assistant"
            content = msg.get("message", "")
            if content:
                messages.append({"role": role, "content": content})

    # Append the current user question
    messages.append({"role": "user", "content": question})

    try:
        reply = _call_groq(messages=messages, max_tokens=1024, temperature=0.3)

        if not reply:
            return "⚠️ The AI returned an empty response. Please try again."

        # Append disclaimer if model didn't include one
        if "disclaimer" not in reply.lower() and "consult" not in reply.lower():
            reply += "\n\n*Disclaimer: This information is for educational purposes only. Always consult a qualified healthcare provider for medical advice.*"

        return reply

    except Exception as e:
        import traceback
        print(f"[RAG] Groq API error in ask_question: {type(e).__name__}: {e}")
        traceback.print_exc()
        return (
            f"⚠️ **AI Chat Error** — Could not get a response from the AI (`{type(e).__name__}`: {str(e)}). "
            "Please check the server console logs for details or verify your API key in the Integrations tab."
        )


def initialize_rag(text: str):
    """Set global document text (legacy helper — prefer passing text directly)."""
    global global_document_text
    global_document_text = text
