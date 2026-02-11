# core/interfaces.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class ILibraryClient(ABC):
    """Interface for library search clients."""
    
    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        resource_type: Optional[str] = None,
        date_from: Optional[int] = None,
        date_to: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Search the library database.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Pagination offset
            resource_type: Filter by resource type (article, book, journal, thesis)
            date_from: Start date filter (YYYY or YYYYMMDD)
            date_to: End date filter (YYYY or YYYYMMDD)
        
        Returns:
            Dictionary containing search results
        """
        pass
