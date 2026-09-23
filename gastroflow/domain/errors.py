class DomainError(Exception):
    """Base exception for business rule failures."""


class AuthenticationError(DomainError):
    """Raised when credentials are invalid."""


class AuthorizationError(DomainError):
    """Raised when a user role cannot perform an action."""


class ConflictError(DomainError):
    """Raised when a unique business rule is violated."""


class ValidationError(DomainError):
    """Raised when input data is invalid for the domain."""
