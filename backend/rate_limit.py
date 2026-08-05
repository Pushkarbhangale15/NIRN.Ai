"""
rate_limit.py — one shared slowapi Limiter instance.

Kept in its own module (rather than inside auth_routes.py) so app.py can
register it on app.state and add the 429 exception handler without a
circular import.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
