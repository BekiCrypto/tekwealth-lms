import logging
import emails # Library for composing and sending emails
from emails.template import JinjaTemplate # For HTML templating
from typing import Dict, Any
import os # For path joining

from backend.core.config import settings # For email server configuration

logger = logging.getLogger(__name__)

# --- Email Sending Logic ---

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Sends an email using configured SMTP settings.
    For MVP, logs to console if SMTP is not fully set up.
    """
    if not settings.EMAIL_HOST or not settings.EMAIL_FROM_ADDRESS:
        logger.warning("Email sending SKIPPED: EMAIL_HOST or EMAIL_FROM_ADDRESS not configured.")
        logger.info(f"Email SKIPPED [To: {to_email}, Subject: {subject}]")
        logger.info(f"Body:\n{html_content[:500]}...") # Log preview of body
        # In a real scenario, you might want to return False or raise an error if config is missing.
        # For this MVP, we'll simulate success if no critical config is missing for "logging" mode.
        return True

    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAIL_FROM_NAME, settings.EMAIL_FROM_ADDRESS)
    )

    smtp_options = {
        "host": settings.EMAIL_HOST,
        "port": settings.EMAIL_PORT,
        "tls": settings.EMAIL_USE_TLS,
        "ssl": settings.EMAIL_USE_SSL, # Note: usually only one of TLS/SSL is true
        "user": settings.EMAIL_USERNAME,
        "password": settings.EMAIL_PASSWORD
    }
    # Remove None values from smtp_options as `emails` library might not like them
    smtp_options = {k: v for k, v in smtp_options.items() if v is not None}
    if not smtp_options.get("user"): # If no username, don't pass empty string for user/password
        smtp_options.pop("user", None)
        smtp_options.pop("password", None)


    logger.info(f"Attempting to send email to {to_email} via {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
    try:
        response = message.send(to=to_email, smtp=smtp_options)
        if response and response.status_code in [250, 252]: # Typical SMTP success codes
            logger.info(f"Email sent successfully to {to_email}. Subject: '{subject}'. SMTP Response: {response.status_code}")
            return True
        else:
            logger.error(f"Failed to send email to {to_email}. SMTP Response: {response.status_code if response else 'No response'}. Error: {response.error if response else 'N/A'}")
            return False
    except Exception as e:
        logger.error(f"Exception during email sending to {to_email}: {e}", exc_info=True)
        return False

def render_email_template(template_name: str, context: Dict[str, Any]) -> str:
    """
    Renders an email template using Jinja2.
    Templates are loaded from the EMAILS_TEMPLATES_DIR.
    """
    # Construct the full path to the template
    # Assumes EMAILS_TEMPLATES_DIR is relative to the project root or an absolute path.
    # If backend.core.config.settings.EMAILS_TEMPLATES_DIR is "backend/templates/emails"
    # and project root is /app, then path is /app/backend/templates/emails

    # A simple way to make path relative to this file's project structure:
    # base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) # Navigate up to project root /app
    # template_full_path = os.path.join(base_dir, settings.EMAILS_TEMPLATES_DIR, template_name)

    # Simpler: if EMAILS_TEMPLATES_DIR is set correctly from project root perspective
    # (e.g. "backend/templates/emails" and app runs from project root)
    # For now, let's assume settings.EMAILS_TEMPLATES_DIR is an accessible path.
    # The `emails` library handles Jinja2 environment setup if template is passed as path string.

    # The `emails` library's JinjaTemplate class expects a string template, not a path directly in constructor.
    # We need to load the file content first.

    # Corrected approach: Load template content from file
    template_file_path = os.path.join(settings.EMAILS_TEMPLATES_DIR, template_name)

    try:
        with open(template_file_path, "r") as f:
            template_str = f.read()

        jinja_template = JinjaTemplate(template_str)
        rendered_html = jinja_template.render(**context) # Pass context variables
        return rendered_html
    except FileNotFoundError:
        logger.error(f"Email template not found: {template_file_path}")
        return f"<p>Error: Email template '{template_name}' not found.</p>" # Fallback content
    except Exception as e:
        logger.error(f"Error rendering email template '{template_name}': {e}", exc_info=True)
        return f"<p>Error rendering email template: {e}</p>" # Fallback content


def send_templated_email(
    to_email: str,
    subject: str, # Subject can also be templated if needed, but kept simple here
    html_template_name: str,
    context: Dict[str, Any]
) -> bool:
    """
    Renders an HTML email template and sends it.
    """
    logger.info(f"Preparing templated email. To: {to_email}, Subject: '{subject}', Template: {html_template_name}")

    # Add common context variables useful for all templates
    context.setdefault("APP_NAME", settings.PROJECT_NAME)
    context.setdefault("APP_FRONTEND_URL", settings.APP_FRONTEND_URL)
    # You could add current year for copyright, etc.
    # context.setdefault("current_year", datetime.utcnow().year)

    html_content = render_email_template(template_name=html_template_name, context=context)

    # Check if rendering failed (e.g., template not found)
    if f"Error: Email template '{html_template_name}' not found." in html_content or \
       "Error rendering email template" in html_content:
        logger.error(f"Aborting email to {to_email} due to template rendering error for '{html_template_name}'.")
        return False # Do not send if template rendering failed

    return send_email(to_email=to_email, subject=subject, html_content=html_content)


# Example Usage (for testing, not part of the actual service):
# if __name__ == "__main__":
#     print("Testing email service...")
#     # Ensure .env has EMAIL_* variables set for a real test.
#     # For console logging, ensure EMAIL_HOST is not set or is empty.
#     if not settings.EMAIL_HOST:
#         print("EMAIL_HOST not set, emails will be logged to console.")

#     test_context = {"user_name": "Test User", "activation_link": "http://example.com/activate"}
#     # Create a dummy template for testing if it doesn't exist
#     dummy_template_path = os.path.join(settings.EMAILS_TEMPLATES_DIR, "test_template.html")
#     if not os.path.exists(settings.EMAILS_TEMPLATES_DIR):
#         os.makedirs(settings.EMAILS_TEMPLATES_DIR)
#     with open(dummy_template_path, "w") as f:
#         f.write("<h1>Hello {{ user_name }}!</h1><p>Activate here: {{ activation_link }}</p><p>Thanks, {{ APP_NAME }}</p>")

#     success = send_templated_email(
#         to_email="test@example.com",
#         subject="Test Email from Platform",
#         html_template_name="test_template.html", # Assuming you create this
#         context=test_context
#     )
#     print(f"Test email send attempt {'succeeded' if success else 'failed'}.")
#     # Clean up dummy template
#     # if os.path.exists(dummy_template_path):
#     #     os.remove(dummy_template_path)
