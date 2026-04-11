import logging
import os

logger = logging.getLogger(__name__)

FROM = "CelDoctor <noreply@celdoctor.com>"


def get_resend():
    import resend as resend_client

    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        logger.warning("RESEND_API_KEY no configurada; emails desactivados")
        return None

    resend_client.api_key = api_key
    return resend_client


def send_email(
    to: list[str],
    subject: str,
    html: str,
):
    resend = get_resend()
    if not resend:
        return

    resend.Emails.send({
        "from": FROM,
        "to": to,
        "subject": subject,
        "html": html,
    })
