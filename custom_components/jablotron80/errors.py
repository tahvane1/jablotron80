"""Errors for the Jablotron component."""

from homeassistant.exceptions import HomeAssistantError


class JablotronException(HomeAssistantError):
    """Base class for Jablotron exceptions."""


class ServiceUnavailable(JablotronException):
    """Service is not available."""


class ModelNotSupported(JablotronException):
    """Model not supported."""


class ShouldNotHappen(JablotronException):
    """This should not happen."""


# API clients translate these identifiers; messages are safe English fallbacks.
CODE_ERROR_MESSAGES = {
    'storage_invalid': 'Personal code storage is invalid.',
    'authentication_required': 'Sign in with an active Home Assistant user account.',
    'permission_denied': 'You do not have permission to control this alarm.',
    'invalid_entity': 'This alarm does not belong to the Jablotron 80 integration.',
    'integration_unavailable': 'The alarm integration is not loaded.',
    'storage_unavailable': 'Personal code storage is unavailable. Use manual PIN entry.',
    'personal_codes_disabled': 'Personal codes are disabled in integration options.',
    'invalid_code': 'The code must contain exactly four digits.',
    'manual_code_required': 'Integration options require manual PIN entry.',
    'code_missing': 'No usable code is available. Use manual PIN entry.',
    'panel_unavailable': 'The alarm panel is unavailable.',
    'invalid_state': 'The alarm cannot be disarmed with a saved code in its current state.',
    'request_pending': 'A request was recently sent. Wait for the alarm state to change.',
    'rate_limited': 'Too many attempts. Wait five minutes or use the physical keypad.',
    'stored_code_invalid': 'A stored personal code is invalid. Migration was stopped.',
    'key_unavailable': 'The encryption key is unavailable or invalid. Use file permissions 0600 or 0400.',
    'key_path_invalid': 'Enter an absolute path to the encryption key file.',
    'key_creation_failed': 'Could not create the encryption key. Check the path and Home Assistant file permissions.',
    'decryption_failed': 'Could not decrypt codes. Check the original key; no fallback code will be used.',
    'stored_credentials_invalid': 'Stored panel credentials are invalid.',
    'invalid_request': 'Invalid request.',
    'invalid_operation': 'Invalid operation.',
    'operation_failed': 'The operation failed. Check integration settings and code storage.',
}


class CodeOperationError(Exception):
    """An expected credential failure with a stable code and no secret details."""

    def __init__(self, code):
        self.code = code
        super().__init__(CODE_ERROR_MESSAGES[code])
