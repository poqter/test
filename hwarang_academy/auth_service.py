"""Compatibility aliases for the unified HWARANG account service."""
from modules.shared.hwarang_auth import (
    HwarangAuthError as AcademyAuthError,
    HwarangAuthService as AcademyAuthService,
    SupabaseConfig,
)

__all__ = ["AcademyAuthError", "AcademyAuthService", "SupabaseConfig"]
