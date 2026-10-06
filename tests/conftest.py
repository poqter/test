"""Tests must not create project API/source/DB traffic, even with real env keys."""
import pytest
import requests


@pytest.fixture(autouse=True)
def block_live_requests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Live HTTP is forbidden in the offline test suite")
    monkeypatch.setattr(requests.Session, "request", blocked)
