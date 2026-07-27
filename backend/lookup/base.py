from abc import ABC, abstractmethod
from typing import Optional

class LookupAdapter(ABC):
    @abstractmethod
    def find_pdf(self, gr_number: str, date: Optional[str] = None, subject: Optional[str] = None) -> Optional[str]:
        """
        Search the department's official website for the GR PDF.
        Returns the absolute URL to the PDF if found, else None.
        """
        pass
