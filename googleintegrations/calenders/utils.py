# utils.py (create this file in your 'calenders' app)
from django.core.mail import send_mail
from django.conf import settings

def send_story_email(user_email, subject, message):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
    )

def send_test_email():
    send_mail(
        'Test Subject',
        'This is a test message.',
        'akibodejoan@gmail.com',  # From email
        ['jga2129@columbia.edu'],  # To email
        fail_silently=False,
    )