from .base import LookupAdapter
from .social_justice import SocialJusticeAdapter
from .default import DefaultAdapter

def get_adapter(department: str) -> LookupAdapter:
    """
    Returns the appropriate adapter for the given department.
    """
    dept_lower = department.lower().replace("_", " ") if department else ""
    if "social justice" in dept_lower:
        return SocialJusticeAdapter()
    return DefaultAdapter()
