import logging
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from .models import ContactMessage

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class ContactMessageView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    """
    API View to handle Send Direct Message form submissions via SMTP
    Supports optional file attachment (multipart/form-data)
    """
    def get(self, request):
        return Response({
            "status": "online",
            "message": "Portfolio Contact API is running. Submit a POST request with name, email, subject, message, and optional attachment."
        }, status=status.HTTP_200_OK)

    def post(self, request):
        data = request.data
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        subject = (data.get('subject') or '').strip()
        message = (data.get('message') or '').strip()
        attachment = request.FILES.get('attachment')  # Optional file

        # Validation
        errors = {}
        if not name:
            errors['name'] = 'Name is required.'
        if not email:
            errors['email'] = 'Email is required.'
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors['email'] = 'Please enter a valid email address.'
        if not message:
            errors['message'] = 'Message is required.'

        if errors:
            return Response({
                "success": False,
                "errors": errors,
                "message": "Please correct the errors in the form."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Fallback subject if left blank
        clean_subject = subject if subject else f"New message from {name} via Portfolio"
        email_subject = f"[Portfolio Contact] {clean_subject}"

        # Create record in DB
        contact_record = ContactMessage.objects.create(
            name=name,
            email=email,
            subject=clean_subject,
            message=message,
        )

        # Format email body
        now_str = timezone.localtime(timezone.now()).strftime('%Y-%m-%d %I:%M %p')
        attachment_line = f"\nAttachment:  {attachment.name} ({_format_size(attachment.size)})\n" if attachment else ""

        email_body = f"""Hello Shobit,

You have received a new direct message from your portfolio contact form.

----------------------------------------------------------------------
SENDER DETAILS
----------------------------------------------------------------------
Name:      {name}
Email:     {email}
Subject:   {clean_subject}
Received:  {now_str}{attachment_line}
----------------------------------------------------------------------
MESSAGE CONTENT
----------------------------------------------------------------------
{message}

----------------------------------------------------------------------
Note: You can click "Reply" directly in your email client to respond to {name} ({email}).
"""

        # Dispatch via SMTP
        try:
            recipient_list = getattr(
                settings,
                'CONTACT_NOTIFICATION_EMAILS',
                [settings.EMAIL_HOST_USER]
            )

            email_msg = EmailMessage(
                subject=email_subject,
                body=email_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipient_list,
                reply_to=[email],
            )

            # Attach file if provided
            if attachment:
                attachment.seek(0)
                email_msg.attach(attachment.name, attachment.read(), attachment.content_type)
                logger.info(f"Attaching file '{attachment.name}' ({_format_size(attachment.size)}) to contact email.")

            email_msg.send(fail_silently=False)

            contact_record.email_sent = True
            contact_record.save(update_fields=['email_sent'])

            return Response({
                "success": True,
                "message": "Your message has been sent successfully! Shobit will reply soon."
            }, status=status.HTTP_201_CREATED)

        except Exception as exc:
            error_details = str(exc)
            logger.exception("Failed to send contact email via SMTP")
            contact_record.email_sent = False
            contact_record.error_message = error_details
            contact_record.save(update_fields=['email_sent', 'error_message'])

            return Response({
                "success": False,
                "message": "Your message was saved, but could not be dispatched via SMTP.",
                "error": error_details
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _format_size(size_bytes):
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"
