from app.security.reset_tokens import (
    extract_prefix,
    hash_reset_token,
    issue_reset_token,
    verify_reset_token,
)


def test_issue_reset_token_returns_prefix_and_raw_token() -> None:
    prefix, raw_token = issue_reset_token()

    assert prefix
    assert len(prefix) == 12
    assert raw_token.startswith(f"{prefix}.")
    assert len(raw_token) > len(prefix) + 1


def test_issued_tokens_are_random() -> None:
    first_prefix, first_token = issue_reset_token()
    second_prefix, second_token = issue_reset_token()

    assert first_prefix != second_prefix
    assert first_token != second_token


def test_extract_prefix_returns_prefix() -> None:
    prefix, raw_token = issue_reset_token()

    assert extract_prefix(raw_token) == prefix


def test_extract_prefix_rejects_malformed_tokens() -> None:
    assert extract_prefix("") is None
    assert extract_prefix("not-a-token") is None
    assert extract_prefix(".secret") is None
    assert extract_prefix("prefix.") is None


def test_hash_and_verify_reset_token() -> None:
    _, raw_token = issue_reset_token()
    _, _, secret = raw_token.partition(".")

    digest = hash_reset_token(secret)

    assert digest != secret
    assert verify_reset_token(secret, digest)
    assert not verify_reset_token("wrong-secret", digest)


def test_verification_rejects_malformed_digest() -> None:
    assert not verify_reset_token("secret", "")
    assert not verify_reset_token("secret", "not-a-valid-pwdlib-hash")
