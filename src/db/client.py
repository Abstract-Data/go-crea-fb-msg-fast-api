"""Supabase client initialization."""

from supabase import create_client, Client

from src.config import get_settings


def get_supabase_client() -> Client:
    """Get Supabase client instance."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)
