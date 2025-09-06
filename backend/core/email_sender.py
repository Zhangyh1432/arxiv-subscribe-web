import smtplib
import os
import io
import zipfile
import re
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

# Basic email validation regex
EMAIL_REGEX = '^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def send_email(files_to_zip, total_papers, recipient_email=None, subject=None):
    """
    Creates a zip file in memory and sends it to a specified or default recipient.
    Returns True if successful, False otherwise.
    """
    load_dotenv()

    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")

    if not all([sender_email, sender_password, smtp_server, smtp_port]):
        logging.error("Email credentials not found in .env file. Please check SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT.")
        return False

    # Determine the recipient
    if recipient_email and re.match(EMAIL_REGEX, recipient_email):
        recipients = [recipient_email]
        logging.info(f"Sending email to custom address: {recipient_email}")
    else:
        recipient_emails_str = os.getenv("RECIPIENT_EMAILS", "")
        recipients = [email.strip() for email in recipient_emails_str.split(',') if email.strip()]
        if not recipients:
            logging.error("No recipient email addresses configured in .env file or provided in the request.")
            return False
        logging.info(f"Sending email to default addresses: {', '.join(recipients)}")

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = ", ".join(recipients)
    email_subject = os.getenv("EMAIL_SUBJECT", "ArXiv Daily Papers")
    message["Subject"] = subject if subject else f"{email_subject} - {total_papers} new papers"

    body = f"Attached is your requested paper analysis." if total_papers == 1 else f"Attached are {total_papers} new papers from your arXiv subscriptions."
    message.attach(MIMEText(body, "plain"))

    # Handle single vs multiple attachments
    if total_papers == 1 and files_to_zip:
        single_file = files_to_zip[0]
        filename = os.path.basename(single_file['filename'])
        attachment = MIMEApplication(single_file['content'].encode('utf-8'), Name=filename)
        attachment['Content-Disposition'] = f'attachment; filename="{filename}"'
        message.attach(attachment)
    elif total_papers > 1:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for file_info in files_to_zip:
                filename = os.path.basename(file_info['filename'])
                zip_f.writestr(filename, file_info['content'].encode('utf-8'))
        
        zip_buffer.seek(0)
        zip_data = zip_buffer.getvalue()

        date_str = datetime.now().strftime('%Y-%m-%d')
        zip_filename = f"arxiv_papers_{date_str}.zip"

        attachment = MIMEApplication(zip_data, Name=zip_filename)
        attachment['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
        message.attach(attachment)

    try:
        logging.info(f"Connecting to SMTP server: {smtp_server}:{smtp_port}")
        if int(smtp_port) == 465:
            with smtplib.SMTP_SSL(smtp_server, int(smtp_port)) as server:
                server.login(sender_email, sender_password)
                server.send_message(message)
        else:
            with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(message)
        
        logging.info(f"Email sent successfully to {', '.join(recipients)}")
        return True
    except Exception as e:
        logging.error("Failed to send email due to an exception.")
        logging.exception(e) # This will log the full traceback
        return False

if __name__ == '__main__':
    # This is a simple test block, configure logging for standalone run
    logging.basicConfig(level=logging.INFO)
    logging.info("Testing email sender...")
    mock_files = [
        {'filename': 'test1.md', 'content': '# Test 1'},
        {'filename': 'test2.md', 'content': '# Test 2'},
    ]
    send_email(mock_files, len(mock_files))
