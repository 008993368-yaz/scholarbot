# core/tools/library_tools.py
from typing import Optional, Any, Dict
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from core.clients.csusb_library_client import CSUSBLibraryClient
from core.utils.logging_utils import get_logger

_log = get_logger(__name__)


class LibrarySearchInput(BaseModel):
    """Input schema for library search tool."""
    query: str = Field(description="Search keywords or phrases to find in library resources")
    resource_type: Optional[str] = Field(
        default=None,
        description="Type of resource to search for: 'article', 'book', 'journal', 'thesis', or None for all types"
    )
    date_from: Optional[int] = Field(
        default=None,
        description="Start year for date range filter (e.g., 2020). Use 4-digit year format."
    )
    date_to: Optional[int] = Field(
        default=None,
        description="End year for date range filter (e.g., 2024). Use 4-digit year format."
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return (1-50)",
        ge=1,
        le=50
    )


@tool(args_schema=LibrarySearchInput)
def get_library_resources(
    query: str,
    resource_type: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Search the CSUSB library for academic resources including articles, books, journals, and dissertations.
    
    Use this tool to find academic papers, books, and other scholarly resources based on user queries.
    You can filter by resource type and date range to refine results.
    
    Args:
        query: Search keywords or phrases (e.g., "machine learning", "climate change")
        resource_type: Filter by type - 'article', 'book', 'journal', 'thesis', or None for all
        date_from: Start year for filtering (e.g., 2020)
        date_to: End year for filtering (e.g., 2024)
        limit: Maximum number of results (1-50)
    
    Returns:
        Formatted string with search results including titles, authors, publication info, and URLs
    """
    _log.info(f"Library search - Query: {query}, Type: {resource_type}, Dates: {date_from}-{date_to}, Limit: {limit}")
    
    try:
        # Initialize client
        client = CSUSBLibraryClient()
        
        # Perform search
        results = client.search(
            query=query,
            limit=limit,
            resource_type=resource_type,
            date_from=date_from,
            date_to=date_to
        )
        
        # Extract and format results
        docs = results.get("docs", [])
        total = results.get("info", {}).get("total", 0)
        
        if not docs:
            return f"No resources found for query: '{query}'. Try broadening your search terms or removing filters."
        
        # Format results for display
        formatted_results = [f"Found {total} resources (showing {len(docs)}):\n"]
        
        for idx, doc in enumerate(docs, 1):
            pnx = doc.get("pnx", {})
            display = pnx.get("display", {})
            
            # Extract key fields
            title = display.get("title", ["Untitled"])[0]
            creators = display.get("creator", [])
            author = creators[0] if creators else "Unknown Author"
            pub_date = display.get("creationdate", [""])[0]
            resource_type_val = display.get("type", [""])[0]
            
            # Get URL
            links = doc.get("delivery", {}).get("link", [])
            url = ""
            for link in links:
                if link.get("displayLabel") == "View Online":
                    url = link.get("linkURL", "")
                    break
            if not url and links:
                url = links[0].get("linkURL", "")
            
            # Format entry
            entry = f"\n{idx}. **{title}**"
            if author:
                entry += f"\n   Author: {author}"
            if pub_date:
                entry += f"\n   Year: {pub_date}"
            if resource_type_val:
                entry += f"\n   Type: {resource_type_val}"
            if url:
                entry += f"\n   URL: {url}"
            
            formatted_results.append(entry)
        
        result_text = "\n".join(formatted_results)
        _log.info(f"Successfully retrieved {len(docs)} results")
        return result_text
        
    except Exception as e:
        error_msg = f"Error searching library: {str(e)}"
        _log.error(error_msg)
        return error_msg


# Export tools list for easy import
LIBRARY_TOOLS = [get_library_resources]
