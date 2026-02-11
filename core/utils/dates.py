# core/utils/dates.py
from datetime import datetime
from typing import Optional

def _get_today_yyyymmdd() -> str:
    """Get today's date in YYYYMMDD format."""
    return datetime.now().strftime("%Y%m%d")

def normalize_date_bound(date_value: Optional[int], is_start: bool) -> str:
    """
    Normalize a date boundary to YYYYMMDD format.
    
    Args:
        date_value: Year (YYYY) or date (YYYYMMDD) as integer
        is_start: True for start date (use Jan 1), False for end date (use Dec 31)
    
    Returns:
        Date string in YYYYMMDD format
    """
    if date_value is None:
        # Return sensible defaults
        if is_start:
            return "19000101"  # Far past for start
        else:
            return _get_today_yyyymmdd()  # Today for end
    
    date_str = str(date_value)
    
    # If it's a 4-digit year
    if len(date_str) == 4:
        if is_start:
            return f"{date_str}0101"  # January 1st
        else:
            return f"{date_str}1231"  # December 31st
    
    # If it's already YYYYMMDD format
    if len(date_str) == 8:
        return date_str
    
    # Invalid format - return safe default
    if is_start:
        return "19000101"
    else:
        return _get_today_yyyymmdd()
