from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
_dummy_password_hash = _password_hash.hash("itds-unavailable-user-dummy-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def verify_dummy_password(password: str) -> bool:
    return _password_hash.verify(password, _dummy_password_hash)
