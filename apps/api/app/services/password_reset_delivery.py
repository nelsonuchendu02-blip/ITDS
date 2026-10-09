from typing import Protocol


class PasswordResetDelivery(Protocol):
    """Delivery boundary for password-reset tokens."""

    def deliver(
        self,
        *,
        email: str,
        reset_token: str,
    ) -> None:
        """Deliver a password-reset token to the account owner."""
        ...