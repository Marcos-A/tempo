"""Password hashing helpers used by the admin login flow."""

from passlib.context import CryptContext


# PBKDF2 is lightweight, widely supported, and sufficient for this internal tool.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password before storing it in the database."""

    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plain password against the stored hash."""

    return pwd_context.verify(plain_password, password_hash)
