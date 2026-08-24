class BookingError(Exception):
    """Base class for all booking-domain errors, mapped to HTTP responses in main.py."""


class NotFoundError(BookingError):
    """Referenced doctor / patient / appointment does not exist. -> 404"""


class ValidationError(BookingError):
    """Request is well-formed but violates a booking rule. -> 400"""


class ConflictError(BookingError):
    """Requested slot is already taken by another booked appointment. -> 409"""


class AlreadyCancelledError(BookingError):
    """Action attempted on an appointment that is already cancelled. -> 400"""
