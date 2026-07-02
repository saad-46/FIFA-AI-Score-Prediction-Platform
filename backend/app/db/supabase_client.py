from functools import lru_cache
from supabase import create_client, Client
from app.core.config import get_settings

settings = get_settings()


@lru_cache()
def get_supabase_client() -> Client:
    """
    Returns a Supabase client using the service role key.
    This bypasses RLS — use only for server-side operations.
    """
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )
