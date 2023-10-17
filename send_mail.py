from flask import Flask, render_template, request
import smtplib
from email.message import EmailMessage

app = Flask(__name__)

EMAIL_ADDRESS = "iamstuarttheminion@gmail.com"
EMAIL_PASSWORD = "aplnoeailycvpgwg"
SMTP_SERVER = 'localhost'
SMTP_PORT = 1025 

def send_email(to_email, subject, message):
    print("in send")

    msg = EmailMessage()
    msg.set_content(message)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg.add_alternative(message, subtype='html')  
    try:
        print("in try")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.set_debuglevel(1)
            smtp.send_message(msg)
            print('Email sent successfully!')
    except Exception as e:
        print(e.msg())


if __name__ == '__main__':
    send_email()