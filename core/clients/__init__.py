# core/clients/__init__.py
"""API clients for ScholarBot."""

from core.clients.csusb_library_client import CSUSBLibraryClient
from core.clients.jev_client import JevClient

__all__ = ["CSUSBLibraryClient", "JevClient"]
