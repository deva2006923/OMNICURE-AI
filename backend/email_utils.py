import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

def log_mock_email(to_email: str, otp: str):
    log_path = os.path.join(os.path.dirname(__file__), "mock_emails.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_path, "a") as f:
            f.write(f"[{timestamp}] To: {to_email} | OTP: {otp}\n")
    except Exception as e:
        print(f"Failed to write mock email log: {e}")

def send_verification_email(to_email: str, otp: str) -> bool:
    load_dotenv(override=True)
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    
    try:
        smtp_port = int(os.getenv("SMTP_PORT") or 465)
    except ValueError:
        smtp_port = 465

    
    if not smtp_email or not smtp_password or smtp_email == "your_gmail@gmail.com" or smtp_password == "your_16_digit_google_app_password":
        raise ValueError("SMTP credentials are not configured in the system settings.")
        
    subject = "OmniCure AI - Account Verification Code"
    body_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.05);">
                <h2 style="color: #4e54c8; text-align: center;">OmniCure AI Portal</h2>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p>Hello,</p>
                <p>Thank you for registering. Please verify your email address to activate your account. Your 6-digit verification code is:</p>
                <div style="font-size: 2rem; font-weight: bold; text-align: center; background: #f0f1ff; color: #4e54c8; padding: 15px; border-radius: 8px; letter-spacing: 5px; margin: 30px 0;">
                    {otp}
                </div>
                <p style="color: #666; font-size: 0.9rem;">This code will expire shortly. If you did not request this code, please ignore this email.</p>
                <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="text-align: center; color: #999; font-size: 0.8rem;">OmniCure AI | Next-gen Medical Report Analysis</p>
            </div>
        </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['From'] = smtp_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))
    
    try:
        # Determine connection strategy based on port
        if smtp_port == 465:
            server_conn = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server_conn = smtplib.SMTP(smtp_host, smtp_port)
            server_conn.starttls()
            
        with server_conn as server:
            server.login(smtp_email, smtp_password)
            server.send_message(msg)
        print(f"SMTP Verification email sent to {to_email} via {smtp_host}:{smtp_port}")
        return True
    except Exception as e:
        print(f"SMTP failed to send email to {to_email} via {smtp_host}:{smtp_port}: {e}")
        raise


