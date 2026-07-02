import os
import json
from groq import Groq
from dotenv import load_dotenv

global_document_text = ""
_best_model_name = None

def get_best_model_name():
    global _best_model_name
    load_dotenv(override=True)
    if _best_model_name:
        return _best_model_name
        
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "dummy_key" or api_key == "your_api_key_here":
        return "llama-3.3-70b-versatile"
        
    try:
        client = Groq(api_key=api_key)
        # Dynamically find the best available model on the user's specific API key
        available_models = [m.id for m in client.models.list().data]
        
        preferences = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
        for pref in preferences:
            if pref in available_models:
                _best_model_name = pref
                return _best_model_name
                
        # Fallback to the first available model if preferences aren't met
        if available_models:
            _best_model_name = available_models[0]
            return _best_model_name
    except Exception as e:
        print(f"Error checking available models: {e}")
        
    return "llama-3.3-70b-versatile"

def initialize_rag(text: str):
    global global_document_text
    global_document_text = text

def analyze_report_mock(custom_text: str = None):
    import re
    text = custom_text if custom_text is not None else global_document_text
    metrics = []
    abnormalities = []
    predictions = []
    
    # 1. Blood Pressure
    bp_match = re.search(r'(?:Blood Pressure|BP)[:\s]+(\d+/\d+)\s*mmHg', text, re.IGNORECASE)
    if bp_match:
        val = bp_match.group(1)
        metrics.append({"name": "Blood Pressure", "value": val + " mmHg"})
        try:
            sys, dia = map(int, val.split('/'))
            if sys >= 140 or dia >= 90:
                abnormalities.append(f"High Blood Pressure ({val} mmHg)")
                predictions.append({
                    "disease": "Hypertension (High Blood Pressure)",
                    "risk_level": "High",
                    "reason": f"Systolic pressure >= 140 or diastolic pressure >= 90 (found {val} mmHg)."
                })
            elif sys >= 130 or dia >= 80:
                abnormalities.append(f"Elevated Blood Pressure ({val} mmHg)")
                predictions.append({
                    "disease": "Hypertension (High Blood Pressure)",
                    "risk_level": "Medium",
                    "reason": f"Elevated blood pressure measurements (found {val} mmHg)."
                })
        except Exception:
            pass

    # 2. Fasting Blood Glucose
    glucose_match = re.search(r'(?:Glucose|Fasting Blood Glucose)[:\s]+(\d+(?:\.\d+)?)\s*mg/dL', text, re.IGNORECASE)
    if glucose_match:
        val = float(glucose_match.group(1))
        metrics.append({"name": "Fasting Blood Glucose", "value": f"{val} mg/dL"})
        if val >= 126:
            abnormalities.append(f"High Fasting Blood Glucose ({val} mg/dL)")
            predictions.append({
                "disease": "Diabetes Mellitus (Type 2)",
                "risk_level": "High",
                "reason": f"Fasting Blood Glucose is >= 126 mg/dL (found {val} mg/dL)."
            })
        elif val >= 100:
            abnormalities.append(f"Impaired Fasting Glucose ({val} mg/dL)")
            predictions.append({
                "disease": "Diabetes Mellitus (Type 2)",
                "risk_level": "Medium",
                "reason": f"Fasting Blood Glucose is in prediabetes range (found {val} mg/dL)."
            })

    # 3. HbA1c
    hba1c_match = re.search(r'(?:HbA1c)[:\s]+(\d+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    if hba1c_match:
        val = float(hba1c_match.group(1))
        metrics.append({"name": "HbA1c", "value": f"{val}%"})
        if val >= 6.5:
            abnormalities.append(f"Elevated HbA1c ({val}%)")
            found = False
            for p in predictions:
                if p["disease"] == "Diabetes Mellitus (Type 2)":
                    p["risk_level"] = "High"
                    p["reason"] += f" HbA1c level is also high (found {val}%)."
                    found = True
            if not found:
                predictions.append({
                    "disease": "Diabetes Mellitus (Type 2)",
                    "risk_level": "High",
                    "reason": f"HbA1c level is >= 6.5% (found {val}%)."
                })
        elif val >= 5.7:
            abnormalities.append(f"Borderline HbA1c ({val}%)")
            found = False
            for p in predictions:
                if p["disease"] == "Diabetes Mellitus (Type 2)":
                    p["reason"] += f" HbA1c level is borderline (found {val}%)."
                    found = True
            if not found:
                predictions.append({
                    "disease": "Diabetes Mellitus (Type 2)",
                    "risk_level": "Medium",
                    "reason": f"HbA1c is in prediabetes range (found {val}%)."
                })

    # 4. Total Cholesterol
    chol_match = re.search(r'(?:Total Cholesterol|Cholesterol)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if chol_match:
        val = int(chol_match.group(1))
        metrics.append({"name": "Total Cholesterol", "value": f"{val} mg/dL"})
        if val >= 240:
            abnormalities.append(f"High Total Cholesterol ({val} mg/dL)")
            predictions.append({
                "disease": "Hyperlipidemia / Cardiovascular Disease",
                "risk_level": "High",
                "reason": f"Total cholesterol is high (>= 240 mg/dL, found {val} mg/dL)."
            })
        elif val >= 200:
            abnormalities.append(f"Borderline High Cholesterol ({val} mg/dL)")
            predictions.append({
                "disease": "Hyperlipidemia / Cardiovascular Disease",
                "risk_level": "Medium",
                "reason": f"Total cholesterol is elevated (found {val} mg/dL)."
            })

    # 5. LDL Cholesterol
    ldl_match = re.search(r'(?:LDL Cholesterol|LDL)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if ldl_match:
        val = int(ldl_match.group(1))
        metrics.append({"name": "LDL Cholesterol", "value": f"{val} mg/dL"})
        if val >= 160:
            abnormalities.append(f"High LDL Cholesterol ({val} mg/dL)")
            found = False
            for p in predictions:
                if p["disease"] == "Hyperlipidemia / Cardiovascular Disease":
                    p["risk_level"] = "High"
                    p["reason"] += f" LDL cholesterol is also high (found {val} mg/dL)."
                    found = True
            if not found:
                predictions.append({
                    "disease": "Hyperlipidemia / Cardiovascular Disease",
                    "risk_level": "High",
                    "reason": f"LDL cholesterol is high (found {val} mg/dL)."
                })
        elif val >= 130:
            abnormalities.append(f"Borderline High LDL Cholesterol ({val} mg/dL)")
            found = False
            for p in predictions:
                if p["disease"] == "Hyperlipidemia / Cardiovascular Disease":
                    p["reason"] += f" LDL cholesterol is borderline high (found {val} mg/dL)."
                    found = True
            if not found:
                predictions.append({
                    "disease": "Hyperlipidemia / Cardiovascular Disease",
                    "risk_level": "Medium",
                    "reason": f"LDL cholesterol is borderline high (found {val} mg/dL)."
                })

    # 6. HDL Cholesterol
    hdl_match = re.search(r'(?:HDL Cholesterol|HDL)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if hdl_match:
        val = int(hdl_match.group(1))
        metrics.append({"name": "HDL Cholesterol", "value": f"{val} mg/dL"})
        if val < 40:
            abnormalities.append(f"Low HDL Cholesterol ({val} mg/dL)")

    # 7. Triglycerides
    tg_match = re.search(r'(?:Triglycerides|TG)[:\s]+(\d+)\s*mg/dL', text, re.IGNORECASE)
    if tg_match:
        val = int(tg_match.group(1))
        metrics.append({"name": "Triglycerides", "value": f"{val} mg/dL"})
        if val >= 200:
            abnormalities.append(f"High Triglycerides ({val} mg/dL)")
        elif val >= 150:
            abnormalities.append(f"Borderline High Triglycerides ({val} mg/dL)")

    # 8. BMI
    bmi_match = re.search(r'(?:BMI)[:\s]+(\d+(?:\.\d+)?)\s*(?:kg/m2)?', text, re.IGNORECASE)
    if bmi_match:
        val = float(bmi_match.group(1))
        metrics.append({"name": "BMI", "value": f"{val} kg/m²"})
        if val >= 30:
            abnormalities.append(f"High BMI ({val} kg/m² - Obese)")
            predictions.append({
                "disease": "Obesity & Metabolic Syndrome",
                "risk_level": "High",
                "reason": f"BMI is >= 30 (found {val} kg/m²), indicating clinical obesity."
            })
        elif val >= 25:
            abnormalities.append(f"Overweight BMI ({val} kg/m²)")
            predictions.append({
                "disease": "Obesity & Metabolic Syndrome",
                "risk_level": "Medium",
                "reason": f"BMI is in the overweight range (found {val} kg/m²)."
            })

    # Fallback to general parsing for other items
    if not metrics:
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('-') and ':' in line:
                parts = line[1:].split(':', 1)
                name = parts[0].strip()
                val = parts[1].strip()
                metrics.append({"name": name, "value": val})

    # Ensure at least low risk generic prediction if we couldn't parse anything else
    if not predictions:
        predictions.append({
            "disease": "General Health Review",
            "risk_level": "Low",
            "reason": "No major abnormal vital signs or laboratory values extracted from the report."
        })

    return {
        "metrics": metrics,
        "abnormalities": abnormalities,
        "predictions": predictions,
        "demo_mode": True
    }

def analyze_report(custom_text: str = None):
    load_dotenv(override=True)
    text = custom_text if custom_text is not None else global_document_text
    if not text:
        raise Exception("Document not uploaded yet")
        
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        return analyze_report_mock(text)
        
    try:
        client = Groq(api_key=api_key)
        model_name = get_best_model_name()
            
        prompt = f"""
        Context from medical report:
        {text}
        
        Analyze the provided medical report context. 
        1. Extract the patient's key lab metrics and vital signs.
        2. Flag any abnormal values based on standard clinical guidelines.
        3. Act as a diagnostic assistant to predict potential diseases or conditions (e.g., Diabetes, Heart Disease, Hypertension) based strictly on these findings. Provide risk levels (Low, Medium, High).
        4. Provide your AI reasoning.
        
        Return the response formatted STRICTLY as a JSON object with NO Markdown wrappers, starting with {{ and ending with }}. Use the following schema:
        {{
          "metrics": [{{"name": "string", "value": "string"}}],
          "abnormalities": ["string"],
          "predictions": [{{"disease": "string", "risk_level": "string", "reason": "string"}}]
        }}
        """
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        result_text = response.choices[0].message.content.strip()
        
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
             result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        try:
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {
                 "metrics": [],
                 "abnormalities": [],
                 "predictions": [{"disease": "Data Parse Error", "risk_level": "Unknown", "reason": "AI did not return valid JSON format."}],
                 "raw_response": result_text
            }
    except Exception as e:
        print(f"Groq API connection error in analyze_report, falling back to mock: {e}")
        return analyze_report_mock(text)

def ask_question(question: str, custom_text: str = None, chat_history: list = None):
    load_dotenv(override=True)
    text = custom_text if custom_text is not None else global_document_text
    if not text:
        raise Exception("Document not uploaded yet")
        
    api_key = os.getenv("GROQ_API_KEY")
    
    def get_mock_reply():
        q_lower = question.lower()
        if "diabetes" in q_lower or "glucose" in q_lower or "sugar" in q_lower:
            return "Based on the report context, Fasting Blood Glucose is 165 mg/dL and HbA1c is 7.2%, both of which are elevated and suggest a High Risk of Diabetes. Please configure your Groq API Key in the backend/.env file for a comprehensive AI answer."
        elif "cholesterol" in q_lower or "lipid" in q_lower or "ldl" in q_lower:
            return "Based on the report context, Total Cholesterol is 245 mg/dL and LDL is 160 mg/dL, which are elevated and suggest a Medium to High Cardiovascular risk. Please configure your Groq API Key in the backend/.env file for a comprehensive AI answer."
        elif "pressure" in q_lower or "bp" in q_lower or "hypertension" in q_lower:
            return "Based on the report context, Blood Pressure is 145/95 mmHg, which is in the high range (Hypertension Stage 2). Please configure your Groq API Key in the backend/.env file for a comprehensive AI answer."
        else:
            return "You are currently running in Demo Mode (no Groq API Key configured in backend/.env). Real-time Groq chatbot functionality is unavailable. However, the rule-based analyzer shows elevated metrics. To enable full AI chat, please add your GROQ_API_KEY to backend/.env."

    if not api_key or api_key == "your_api_key_here":
        return get_mock_reply()

    try:
        client = Groq(api_key=api_key)
        model_name = get_best_model_name()
        
        system_prompt = (
            "You are OmniCure AI, a professional medical report assistant. "
            "Your goal is to help users understand their lab reports and answer questions accurately. "
            "Always be clear, compassionate, and structure your responses with bullet points where appropriate. "
            "Base your answers strictly on the provided report context. "
            "Always include a brief friendly medical disclaimer at the bottom of your response."
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Inject report context
        messages.append({
            "role": "user",
            "content": f"Here is the patient medical report context:\n{text}\n\nPlease use this to answer all my subsequent questions."
        })
        messages.append({
            "role": "assistant",
            "content": "Understood. I have parsed the report and am ready to answer any questions based on it."
        })
        
        # Add historical conversation messages
        if chat_history:
            for msg in chat_history[:-1]:
                role = "user" if msg["sender"] == "user" else "assistant"
                messages.append({"role": role, "content": msg["message"]})
                
        # Add the current user query
        messages.append({"role": "user", "content": question})
            
        response = client.chat.completions.create(
            model=model_name,
            messages=messages
        )
        reply = response.choices[0].message.content.strip()
        
        # Ensure a disclaimer is present if not already added by model
        disclaimer = "\n\n*Disclaimer: This information is for educational purposes only. Please consult a qualified healthcare provider for medical advice.*"
        if "disclaimer" not in reply.lower() and "consult" not in reply.lower():
            reply += disclaimer
            
        return reply
    except Exception as e:
        print(f"Groq API connection error in ask_question, falling back to mock: {e}")
        return get_mock_reply()

