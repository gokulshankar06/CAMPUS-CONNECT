import os
import smtplib
from email.message import EmailMessage
from flask import current_app

def send_email(to_email, otp_code):
    """
    Send OTP email with proper error handling
    """
    try:
        msg = EmailMessage()
        msg['Subject'] = 'Your OTP Code'
        msg['From'] = current_app.config.get('MAIL_USERNAME')
        msg['To'] = to_email
        
        # Email body
        body = f"""
        <h2>Your OTP Code</h2>
        <p>Your one-time password (OTP) is: <strong>{otp_code}</strong></p>
        <p>This code will expire in 10 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
        """
        
        msg.set_content(body, subtype='html')
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(
                current_app.config.get('MAIL_USERNAME'),
                current_app.config.get('MAIL_PASSWORD')
            )
            smtp.send_message(msg)
            
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending email: {str(e)}")
        return False
