"""Provider interface for the channels Odoo Community cannot deliver itself: sms, push and electronic registered mail.

The prototype only ships mock providers: they log the message and return a fictitious reference, so nothing
leaves the server. A real provider is a subclass registered in PROVIDERS and chosen with the system
parameter vme_belgie.<kind>_provider (see docs/dev/communicatie.md).
"""
import logging
import uuid

_logger = logging.getLogger(__name__)


class SmsProvider:
    """Send one text message to one phone number; return the provider's reference."""

    def __init__(self, env):
        self.env = env

    def send(self, number, text):
        raise NotImplementedError


class PushProvider:
    """Send a push notification to the app of a person (stap 15: the owner portal)."""

    def __init__(self, env):
        self.env = env

    def can_reach(self, partner):
        """True if the partner has an app or portal account that receives notifications."""
        raise NotImplementedError

    def send(self, partner, title, text):
        raise NotImplementedError


class RegisteredMailProvider:
    """Hand a PDF to a service for electronic registered delivery and follow its status."""

    def __init__(self, env):
        self.env = env

    def submit(self, registered_mail, pdf_content):
        """Return the tracking reference of the deposit."""
        raise NotImplementedError

    def get_status(self, reference):
        """Return one of 'deposited', 'delivered' or 'returned'."""
        raise NotImplementedError


def _mock_reference(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


class MockSmsProvider(SmsProvider):
    def send(self, number, text):
        reference = _mock_reference("MOCK-SMS")
        _logger.info("Mock sms %s to %s: %s", reference, number, text)
        return reference


class MockPushProvider(PushProvider):
    def can_reach(self, partner):
        # Until the portal of step 15 exists, only people with a portal or internal user count as reachable.
        return bool(partner.user_ids)

    def send(self, partner, title, text):
        reference = _mock_reference("MOCK-PUSH")
        _logger.info("Mock push %s to %s: %s - %s", reference, partner.display_name, title, text)
        return reference


class MockRegisteredMailProvider(RegisteredMailProvider):
    def submit(self, registered_mail, pdf_content):
        reference = _mock_reference("MOCK-ERDS")
        _logger.info("Mock electronic registered mail %s for %s (%s bytes)",
                     reference, registered_mail.partner_id.display_name, len(pdf_content or b""))
        return reference

    def get_status(self, reference):
        return "delivered"


PROVIDERS = {
    "sms": {"mock": MockSmsProvider},
    "push": {"mock": MockPushProvider},
    "registered": {"mock": MockRegisteredMailProvider},
}


def get_provider(env, kind):
    """The provider configured for this kind of channel (system parameter vme_belgie.<kind>_provider)."""
    code = env["ir.config_parameter"].sudo().get_param(f"vme_belgie.{kind}_provider") or "mock"
    provider_class = PROVIDERS[kind].get(code) or PROVIDERS[kind]["mock"]
    return provider_class(env)
