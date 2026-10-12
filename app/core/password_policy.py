from __future__ import annotations

import secrets
import string

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


def password_issues(password: str, username: str | None = None) -> list[str]:
    """Return policy violations without logging or echoing the password."""
    issues: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        issues.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long")
    if len(password) > PASSWORD_MAX_LENGTH:
        issues.append(f"Password must be no more than {PASSWORD_MAX_LENGTH} characters long")

    categories = sum(
        (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
    )
    if categories < 3:
        issues.append("Password must use at least three character types")

    if password and len(set(password)) == 1:
        issues.append("Password cannot consist of one repeated character")

    if username and len(username) >= 3 and username.casefold() in password.casefold():
        issues.append("Password must not contain the username")

    return issues


def validate_password(password: str, username: str | None = None) -> None:
    issues = password_issues(password, username)
    if issues:
        raise ValueError("; ".join(issues))


def generate_password(length: int = 28) -> str:
    """Generate a strong, printable password satisfying the local password policy."""
    if length < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Generated passwords must be at least {PASSWORD_MIN_LENGTH} characters")

    groups = (string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^&*()-_=+")
    chars = [secrets.choice(group) for group in groups[:3]]
    alphabet = "".join(groups)
    chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)
