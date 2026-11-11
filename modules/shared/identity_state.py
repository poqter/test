"""Drop protected work when identity/authorization changes, never on token rotation."""
from __future__ import annotations


def fingerprint(identity):
    identity = identity or {}
    profile = identity.get('profile') or {}
    return (
        profile.get('id'), profile.get('role'), profile.get('is_active'),
        profile.get('organization_unit_id'), profile.get('position_code'),
        tuple(sorted((identity.get('app_access') or {}).items())),
        tuple(sorted(identity.get('feature_permissions') or ())),
    )


def clear_protected_state(session, *, keep_device=False):
    # Only deployment routing and (for the same user) device credentials survive.
    keep = {'_calendar_deployment'}
    if keep_device:
        keep.update({'device_handle', 'device_action', 'device_restored',
                     'device_check_pending', 'device_rotation_pending', 'hw_device_bridge'})
    saved = {key: session[key] for key in keep if key in session}
    session.clear()
    session.update(saved)


def reconcile_identity(session, previous, current):
    """Return True when callers must rebuild the full shell before showing data."""
    if not previous or fingerprint(previous) == fingerprint(current):
        return False
    same_user = (previous.get('profile') or {}).get('id') == (current.get('profile') or {}).get('id')
    had_device = bool(session.get('device_handle'))
    clear_protected_state(session, keep_device=same_user)
    if not same_user and had_device:
        session['device_action'] = 'clear'
    return True
