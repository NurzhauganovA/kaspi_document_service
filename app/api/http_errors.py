from fastapi import (
    HTTPException,
    status,
)

from app.domain.exceptions import (
    AuthenticationError,
    DomainError,
    EmptyQueueError,
    InvalidDocumentStateError,
)


def raise_for_domain(exc: DomainError) -> None:
    if isinstance(exc, AuthenticationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        )
    if isinstance(exc, EmptyQueueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    if isinstance(exc, InvalidDocumentStateError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
