"""Process-local, one-use launch grants and calculator-scoped one-hour leases.

No password, customer data or credentials are stored in URLs. Server restart
invalidates grants. Intended for the existing single-process Streamlit deployment.
"""
from dataclasses import dataclass
import hashlib
import secrets
import threading
import time
import streamlit as st

LIFETIME = 3600
CLAIM_WINDOW = 90

@dataclass(frozen=True)
class Grant:
    owner: str
    calculator: str
    tab: str
    issued: float
    expires: float


class AccessStore:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.grants = {}
        self.leases = {}

    @staticmethod
    def digest(token):
        if not isinstance(token, str) or not 20 <= len(token) <= 128:
            return None
        return hashlib.sha256(token.encode()).hexdigest()

    def prune(self):
        now = self.clock()
        self.grants = {k: g for k, g in self.grants.items() if now < min(g.expires, g.issued + CLAIM_WINDOW)}
        self.leases = {k: g for k, g in self.leases.items() if now < g.expires}

    def issue(self, owner, calculator, tab):
        if not owner or not calculator or not isinstance(tab, str) or not 16 <= len(tab) <= 80:
            raise ValueError('Invalid launch request')
        with self.lock:
            self.prune()
            # Keep issuance bounded without discarding active leases.
            pending = [k for k,g in self.grants.items() if g.owner == owner]
            if len(pending) >= 100:
                for k in pending[:-80]: self.grants.pop(k, None)
            now = self.clock()
            grant = Grant(owner, calculator, tab, now, now + LIFETIME)
            token = secrets.token_urlsafe(32)
            self.grants[self.digest(token)] = grant
            return token, grant

    def redeem(self, token, calculator, tab):
        with self.lock:
            self.prune()
            key = self.digest(token)
            grant = self.grants.get(key)
            if not grant or grant.calculator != calculator or grant.tab != tab:
                return None
            del self.grants[key]  # Atomic consumption: exactly one concurrent winner.
            lease = secrets.token_urlsafe(32)
            self.leases[self.digest(lease)] = grant
            return lease, grant

    def validate(self, token, calculator, tab):
        with self.lock:
            self.prune()
            grant = self.leases.get(self.digest(token))
            if not grant or grant.calculator != calculator or grant.tab != tab:
                return None
            return grant

    def revoke_owner(self, owner):
        with self.lock:
            self.grants = {k:g for k,g in self.grants.items() if g.owner != owner}
            self.leases = {k:g for k,g in self.leases.items() if g.owner != owner}


@st.cache_resource
def access_store():
    return AccessStore()
