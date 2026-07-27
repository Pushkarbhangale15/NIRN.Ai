from typing import Optional
from .base import LookupAdapter
from .portal_lookup import verify_predictable_url, search_government_portal

class DefaultAdapter(LookupAdapter):
    def find_pdf(self, gr_number: str, date: Optional[str] = None, subject: Optional[str] = None) -> Optional[str]:
        # 1. Attempt direct verification of predictable pattern
        url = verify_predictable_url(gr_number)
        if url:
            return url
            
        # 2. Attempt searching the government portal
        url = search_government_portal(gr_number, "Default", date, subject)
        if url:
            return url
            
        return None
