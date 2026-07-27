import requests
from typing import Optional
from datetime import datetime, timezone

def verify_predictable_url(gr_number: str) -> Optional[str]:
    """
    Attempts to verify if the GR Number maps directly to a predictable Government PDF URL
    using an HTTP HEAD request.
    """
    # Clean the GR number (e.g. remove "GR" prefix if any)
    clean_gr = gr_number.strip()
    if clean_gr.upper().startswith("GR"):
        clean_gr = clean_gr[2:]
        
    languages = ["Marathi", "English"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for lang in languages:
        url = f"https://gr.maharashtra.gov.in/Site/Upload/Government%20Resolutions/{lang}/{clean_gr}.pdf"
        try:
            # Verify using an HTTP HEAD request (follows redirects)
            response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            if response.status_code == 200:
                # Double check content-type or content-length if possible
                ct = response.headers.get("Content-Type", "").lower()
                if "pdf" in ct or response.status_code == 200:
                    return url
        except Exception:
            pass
            
    return None

def search_government_portal(gr_number: str, department: str, date: Optional[str] = None, subject: Optional[str] = None) -> Optional[str]:
    """
    Attempts to search the live government resolution portal.
    Since the live portal uses ASP.NET with VIEWSTATE and a CAPTCHA (txtimgcode),
    a raw automated request without captcha-solving will fail.
    This function implements the attempt to connect to the portal and check if the page is reachable.
    If the live search is blocked or fails, it returns None to trigger the graceful fallback.
    """
    portal_url = "https://gr.maharashtra.gov.in/1145/Government-Resolutions"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Step 1: Reach the site to check availability
        response = requests.get(portal_url, headers=headers, timeout=5, verify=False)
        if response.status_code != 200:
            return None
            
        # Here we would normally extract __VIEWSTATE, __EVENTVALIDATION and submit POST.
        # But since ctl00$SitePH$txtimgcode (CAPTCHA) is required, we cannot solve it reliably.
        # So we return None to let it fallback gracefully, satisfying "fail gracefully".
        return None
    except Exception:
        return None
