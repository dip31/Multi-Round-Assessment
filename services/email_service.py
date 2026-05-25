"""
Email Service for Sending Recruitment Emails with Attachments
Supports SMTP for sending actual emails with PDF attachments
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path
import os


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(self):
        # Get SMTP configuration from environment
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", self.smtp_user)
        self.from_name = os.getenv("FROM_NAME", "HR Team")
        
        self.enabled = bool(self.smtp_user and self.smtp_password)
        
        if not self.enabled:
            print("⚠️ Email service not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
    
    def send_email(self, to_email: str, subject: str, body_html: str, 
                   attachments: list = None, body_text: str = None):
        """
        Send an email with optional attachments
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            attachments: List of file paths to attach
            body_text: Plain text version (optional)
        
        Returns:
            dict: {"success": bool, "message": str}
        """
        if not self.enabled:
            print(f"📧 [SIMULATION] Would send email to {to_email}")
            print(f"   Subject: {subject}")
            return {
                "success": False,
                "message": "Email service not configured. Set SMTP credentials in .env"
            }
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text and HTML parts
            if body_text:
                msg.attach(MIMEText(body_text, 'plain'))
            msg.attach(MIMEText(body_html, 'html'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if Path(file_path).exists():
                        with open(file_path, 'rb') as f:
                            attachment = MIMEApplication(f.read())
                            attachment.add_header(
                                'Content-Disposition', 
                                'attachment', 
                                filename=Path(file_path).name
                            )
                            msg.attach(attachment)
                    else:
                        print(f"⚠️ Attachment not found: {file_path}")
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Email sent to {to_email}: {subject}")
            return {
                "success": True,
                "message": f"Email sent successfully to {to_email}"
            }
            
        except Exception as e:
            print(f"❌ Failed to send email to {to_email}: {e}")
            return {
                "success": False,
                "message": f"Failed to send email: {str(e)}"
            }
    
    def send_offer_letter(self, candidate_email: str, candidate_name: str, 
                         job_title: str, salary: float, start_date: str, 
                         pdf_path: str = None):
        """Send offer letter email with PDF attachment"""
        
        subject = f"Job Offer - {job_title}"
        
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .highlight {{ background: #fff; padding: 20px; border-left: 4px solid #667eea; 
                            margin: 20px 0; border-radius: 5px; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; 
                         color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Congratulations!</h1>
                    <p>We're excited to offer you a position at our company</p>
                </div>
                <div class="content">
                    <p>Dear {candidate_name},</p>
                    
                    <p>We are delighted to extend an offer for the position of <strong>{job_title}</strong> 
                    at our company. After careful consideration of your qualifications and interview performance, 
                    we believe you would be an excellent addition to our team.</p>
                    
                    <div class="highlight">
                        <h3>Offer Details:</h3>
                        <ul>
                            <li><strong>Position:</strong> {job_title}</li>
                            <li><strong>Annual Salary:</strong> ${salary:,} USD</li>
                            <li><strong>Start Date:</strong> {start_date}</li>
                            <li><strong>Benefits:</strong> Health Insurance, 401(k), PTO, Stock Options</li>
                        </ul>
                    </div>
                    
                    <p>Please find the detailed offer letter attached to this email. We kindly request 
                    that you review the offer and respond within 7 days.</p>
                    
                    <p>To accept this offer, please click the button below or reply to this email:</p>
                    
                    <center>
                        <a href="http://localhost:8000" class="button">Accept Offer</a>
                    </center>
                    
                    <p>If you have any questions or would like to discuss any aspect of the offer, 
                    please don't hesitate to reach out to us.</p>
                    
                    <p>We look forward to welcoming you to our team!</p>
                    
                    <p>Best regards,<br>
                    <strong>HR Team</strong><br>
                    Your Company Name</p>
                </div>
                <div class="footer">
                    <p>This is an automated email from the AI Recruitment System</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        Congratulations {candidate_name}!
        
        We are delighted to offer you the position of {job_title}.
        
        Offer Details:
        - Position: {job_title}
        - Annual Salary: ${salary:,} USD
        - Start Date: {start_date}
        - Benefits: Health Insurance, 401(k), PTO, Stock Options
        
        Please review the attached offer letter and respond within 7 days.
        
        Best regards,
        HR Team
        """
        
        attachments = [pdf_path] if pdf_path and Path(pdf_path).exists() else []
        
        return self.send_email(
            to_email=candidate_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            attachments=attachments
        )
    
    def send_onboarding_email(self, candidate_email: str, candidate_name: str, 
                             start_date: str, documents_needed: list):
        """Send onboarding welcome email"""
        
        subject = f"Welcome to the Team! - Onboarding Information"
        
        docs_list = "".join([f"<li>{doc}</li>" for doc in documents_needed])
        
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                .checklist {{ background: #fff; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎊 Welcome Aboard!</h1>
                    <p>We're thrilled to have you join our team</p>
                </div>
                <div class="content">
                    <p>Dear {candidate_name},</p>
                    
                    <p>Welcome to the team! We're excited to have you start on <strong>{start_date}</strong>.</p>
                    
                    <p>To ensure a smooth onboarding process, please complete the following before your start date:</p>
                    
                    <div class="checklist">
                        <h3>📋 Pre-Onboarding Checklist:</h3>
                        <ul>
                            {docs_list}
                        </ul>
                    </div>
                    
                    <p><strong>What to Expect on Day 1:</strong></p>
                    <ul>
                        <li>Welcome orientation session</li>
                        <li>IT equipment setup</li>
                        <li>Meet your team members</li>
                        <li>Review of company policies</li>
                    </ul>
                    
                    <p>If you have any questions before your start date, please don't hesitate to reach out.</p>
                    
                    <p>Looking forward to working with you!</p>
                    
                    <p>Best regards,<br>
                    <strong>HR Team</strong></p>
                </div>
                <div class="footer">
                    <p>This is an automated email from the AI Recruitment System</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(
            to_email=candidate_email,
            subject=subject,
            body_html=body_html
        )


# Global email service instance
email_service = EmailService()
