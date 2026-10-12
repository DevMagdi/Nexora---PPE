from __future__ import annotations

import pytest

from app.core.password_policy import generate_password, password_issues, validate_password


def test_policy_rejects_short_simple_and_username_passwords():
    assert password_issues("short")
    assert password_issues("aaaaaaaaaaaa")
    assert password_issues("adminStrongPass!2026", "admin")
    with pytest.raises(ValueError):
        validate_password("simple-password")


def test_generated_passwords_satisfy_policy():
    for _ in range(100):
        password = generate_password()
        assert len(password) >= 12
        assert password_issues(password) == []
