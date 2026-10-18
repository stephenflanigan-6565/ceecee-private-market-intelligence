"""Explicit, one-shot authorization diagnostic; never imported by app startup.

No export, database access, credential mutation or raw response logging.
Only fixed identifiers and bounded HTTP status reach the result.
"""
import json
import urllib.error
import urllib.request

from pmi_google_drive import GoogleDriveClient, DriveError, _NoRedirect

ERROR_BODY_LIMIT = 4096
PROVIDER_ERRORS = frozenset({
    'invalid_grant', 'invalid_client', 'unauthorized_client', 'invalid_request',
    'unsupported_grant_type', 'invalid_scope', 'access_denied',
    'temporarily_unavailable', 'server_error', 'invalid_token',
    'UNAUTHENTICATED', 'PERMISSION_DENIED', 'INVALID_ARGUMENT',
    'RESOURCE_EXHAUSTED', 'UNAVAILABLE', 'INTERNAL',
    'authError', 'insufficientPermissions', 'accessNotConfigured',
    'rateLimitExceeded', 'userRateLimitExceeded',
})
CLIENT_ERRORS = frozenset({
    'drive_credentials_missing', 'invalid_oauth_response', 'unexpected_oauth_scope',
    'invalid_drive_response', 'drive_transport_error', 'drive_identity_unavailable',
    'response_too_large', 'invalid_content_length', 'redirect_not_allowed',
    'provider_error_unclassified',
})

def safe_status(value):
    return value if type(value) is int and 100 <= value <= 599 else None

def provider_identifier(response):
    try:
        raw = response.read(ERROR_BODY_LIMIT + 1)
        if len(raw) > ERROR_BODY_LIMIT: return 'provider_error_unclassified'
        data = json.loads(raw)
        error = data.get('error') if isinstance(data, dict) else None
        candidates = [error] if isinstance(error, str) else []
        if isinstance(error, dict):
            candidates.append(error.get('status'))
            entries = error.get('errors')
            if isinstance(entries, list):
                candidates.extend(e.get('reason') for e in entries if isinstance(e, dict))
        return next((v for v in candidates if isinstance(v, str) and v in PROVIDER_ERRORS),
                    'provider_error_unclassified')
    except Exception:
        return 'provider_error_unclassified'

class DiagnosticOpener:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    def open(self, request, timeout):
        identifier = None
        status = None
        try:
            response = self.opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            try:
                status = safe_status(error.code)
                identifier = provider_identifier(error)
            finally:
                error.close()
        else:
            status = safe_status(getattr(response, 'status', 200))
            if status is not None and 200 <= status < 300: return response
            try: identifier = provider_identifier(response)
            finally: response.close()
        # Raise outside the handler, so raw HTTPError is not retained as context.
        raise DriveError(identifier, status) from None

def diagnose(environment=None, *, opener=None):
    stage = 'token_refresh'
    try:
        client = GoogleDriveClient.from_environment(environ=environment,
            opener=DiagnosticOpener(opener))
        client._token()  # One refresh only; identity reuses this in-memory token.
        stage = 'drive_identity'
        client.identity()
        return {'stage': stage, 'error_identifier': None, 'http_status': 200}
    except DriveError as error:
        identifier = error.code if error.code in PROVIDER_ERRORS | CLIENT_ERRORS else 'provider_error_unclassified'
        return {'stage': stage, 'error_identifier': identifier,
                'http_status': safe_status(error.http_status)}
    except Exception:
        return {'stage': stage, 'error_identifier': 'diagnostic_internal_error', 'http_status': None}

if __name__ == '__main__':
    print(json.dumps(diagnose(), sort_keys=True))
