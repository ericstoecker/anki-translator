"""Configuration for the Anki Translator sync add-on."""

# These should be set by the user in the add-on config dialog or config.json
DEFAULTS = {
    "backend_url": "https://anki-translator.example.com",
    "api_token": "",  # JWT token from logging in to the backend
    "auto_sync_on_startup": True,
    "trigger_ankiweb_sync_after": False,
}


def get_config():
    """Get add-on config, merging with defaults."""
    try:
        from aqt import mw

        config = mw.addonManager.getConfig(__name__) or {}
    except Exception:
        config = {}

    merged = dict(DEFAULTS)
    merged.update(config)
    return merged
