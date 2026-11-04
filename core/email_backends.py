"""A Django email backend that sends via Resend's HTTP API.

Outbound SMTP (even on port 587) is blocked or silently dropped by some
PaaS hosts for anti-spam reasons - that's what happened on Render here:
smtp.resend.com was reachable fine from outside, but the live app's own
SMTP connection attempt just hung until gunicorn's worker timeout killed
it. Resend's HTTP API is ordinary HTTPS on port 443, which essentially
every host allows outbound, so it sidesteps the problem entirely. Uses
only the standard library, matching nutrition.ai_client's approach to
Gemini - no SDK dependency for one API call.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
REQUEST_TIMEOUT_SECONDS = 15


class ResendAPIBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY is not set.")
            return 0
        logger.info("ResendAPIBackend: sending %d message(s) with key prefix %s...", len(email_messages), api_key[:6])

        sent_count = 0
        for message in email_messages:
            if self._send_one(message, api_key):
                sent_count += 1
        return sent_count

    def _send_one(self, message, api_key):
        payload = {
            "from": message.from_email,
            "to": list(message.to),
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)

        request = urllib.request.Request(
            RESEND_ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                status = response.status
                body = response.read().decode("utf-8", errors="replace")
            logger.info("ResendAPIBackend: to=%s status=%s body=%s", payload["to"], status, body[:500])
            return True
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            logger.error("ResendAPIBackend: HTTP %s from Resend for to=%s: %s", exc.code, payload["to"], error_body[:500])
            if not self.fail_silently:
                raise
            return False
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.error("ResendAPIBackend: network error for to=%s: %s", payload["to"], exc)
            if not self.fail_silently:
                raise
            return False
