"""Domain-level errors — mapped to HTTP responses in controllers."""


class DomainError(Exception):
    """Base class for business rule violations."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class AuthenticationError(DomainError):
    """Invalid credentials."""


class PermissionDeniedError(DomainError):
    """Caller lacks required role or ownership."""


class EmptyQueueError(DomainError):
    """No pending documents available to claim."""


class DocumentNotFoundError(DomainError):
    """Document does not exist."""


class InvalidDocumentStateError(DomainError):
    """Document is not in the expected state for this operation."""
