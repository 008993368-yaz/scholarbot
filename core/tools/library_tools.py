# core/tools/library_tools.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from core.clients.csusb_library_client import CSUSBLibraryClient
from core.services.result_formatter import ResultFormatter
from core.utils.logging_utils import get_logger

_log = get_logger(__name__)


class LibrarySearchInput(BaseModel):
    """Input schema for library search tool."""

    query: str = Field(description="Search keywords or phrases to find in library resources")
    resource_type: Optional[str] = Field(
        default=None,
        description=(
            "Type of resource to search for: 'article', 'book', 'journal', "
            "'thesis', or None for all types"
        ),
    )
    date_from: Optional[int] = Field(
        default=None,
        description="Start year for date range filter (e.g., 2020). Use 4-digit year format.",
    )
    date_to: Optional[int] = Field(
        default=None,
        description="End year for date range filter (e.g., 2024). Use 4-digit year format.",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of results to return (1-50)",
        ge=1,
        le=50,
    )


def run_library_search(
    query: str,
    resource_type: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Search Primo and return structured rows plus a text summary for the LLM.

    Returns:
        dict with keys: total (int), rows (list[dict]), text (str)
    """
    _log.info(
        "Library search - Query: %s, Type: %s, Dates: %s-%s, Limit: %s",
        query,
        resource_type,
        date_from,
        date_to,
        limit,
    )

    client = CSUSBLibraryClient()
    results = client.search(
        query=query,
        limit=limit,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
    )

    docs = results.get("docs", [])
    total = results.get("info", {}).get("total", 0)

    if not docs:
        text = (
            f"No resources found for query: '{query}'. "
            "Try broadening your search terms or removing filters."
        )
        return {"total": 0, "rows": [], "text": text}

    rows: List[Dict[str, Any]] = ResultFormatter.format_table_data(docs)
    lines = [f"Found {total} resources (showing {len(docs)}):\n"]
    for row in rows:
        entry = f"\n{row['#']}. **{row['Title']}**"
        if row.get("Authors") and row["Authors"] != "N/A":
            entry += f"\n   Author: {row['Authors']}"
        if row.get("Year") and row["Year"] != "N/A":
            entry += f"\n   Year: {row['Year']}"
        if row.get("Type") and row["Type"] != "N/A":
            entry += f"\n   Type: {row['Type']}"
        if row.get("Link"):
            entry += f"\n   URL: {row['Link']}"
        lines.append(entry)

    text = "\n".join(lines)
    _log.info("Successfully retrieved %s results", len(docs))
    return {"total": total, "rows": rows, "text": text}


@tool(args_schema=LibrarySearchInput)
def get_library_resources(
    query: str,
    resource_type: Optional[str] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    limit: int = 10,
) -> str:
    """
    Search the CSUSB library for academic resources including articles, books,
    journals, and dissertations.

    Use this tool to find academic papers, books, and other scholarly resources
    based on user queries. You can filter by resource type and date range.
    """
    try:
        return run_library_search(
            query=query,
            resource_type=resource_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )["text"]
    except Exception as e:
        error_msg = f"Error searching library: {e}"
        _log.error(error_msg)
        return error_msg


LIBRARY_TOOLS = [get_library_resources]
