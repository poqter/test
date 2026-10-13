"""Bounded provider diagnostics without headers, request bodies or credentials."""
import os
import re


def safe_message(value):
    text = str(value or '')[:4000]
    for name, secret in os.environ.items():
        if any(part in name.upper() for part in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD')) and len(secret) >= 8:
            text = text.replace(secret, '[redacted]')
    text = re.sub(r'(?i)Bearer\s+\S+|sk-[A-Za-z0-9_-]+', '[redacted]', text)
    text = re.sub(r'https?://\S+', '[url redacted]', text)
    text = re.sub(r'[\w.+-]+@[\w.-]+', '[email redacted]', text)
    return re.sub(r'[\x00-\x1f]', ' ', text)[:500]


def request_diagnostic(response=None, exc=None, kind=None):
    status = getattr(response, 'status_code', None)
    details = {'http_status': status if isinstance(status, int) else None,
               'error_class': kind or ('http_error' if response is not None else type(exc).__name__),
               'provider_error_code': None, 'provider_error_type': None}
    if response is not None:
        try:
            data = response.json()
            error = data.get('error') if isinstance(data, dict) else None
            if isinstance(error, dict):
                for field in ('code', 'type'):
                    value = error.get(field)
                    if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}', value):
                        details['provider_error_' + field] = value
                details['provider_message'] = safe_message(error.get('message'))
        except (ValueError, TypeError):
            pass
    return details


def request_message(stage, details):
    suffix = f"HTTP {details['http_status']}" if details.get('http_status') else details['error_class']
    return safe_message(f"OpenAI {stage}: {suffix}; {details.get('provider_error_code') or ''}; {details.get('provider_message') or ''}")
