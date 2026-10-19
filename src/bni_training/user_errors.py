from __future__ import annotations


class UserFacingError(ValueError):
    """An error whose message is safe and helpful to show to a workshop participant as is."""
