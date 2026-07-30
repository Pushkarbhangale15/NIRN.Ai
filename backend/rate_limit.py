"""rate_limit.py — shared slowapi Limiter instance.

Lives in its own module so both app.py (registers it on the FastAPI app)
and routes.py (decorates individual endpoints) can import it without a
circular import.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
