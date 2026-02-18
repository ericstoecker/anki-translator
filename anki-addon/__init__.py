"""Anki Translator Sync Add-on.

Syncs flashcards between the Anki Translator cloud backend and Anki.
"""

from aqt import mw, gui_hooks
from aqt.qt import QAction
from aqt.utils import showInfo, showWarning, tooltip

from .config import get_config
from .sync import AnkiTranslatorSync


def run_sync():
    """Execute the full sync flow."""
    config = get_config()
    if not config.get("api_token"):
        showWarning(
            "Anki Translator: No API token configured.\n"
            "Please set your API token in the add-on configuration."
        )
        return

    syncer = AnkiTranslatorSync(config["backend_url"], config["api_token"])

    try:
        mw.progress.start(label="Syncing with Anki Translator...")
        results = syncer.full_sync(mw)
        mw.progress.finish()
        mw.reset()

        tooltip(
            f"Anki Translator sync complete: "
            f"{results.get('pulled', 0)} pulled, "
            f"{results.get('pushed', 0)} pushed"
        )
    except Exception as e:
        mw.progress.finish()
        showWarning(f"Anki Translator sync failed:\n{e}")


def on_profile_loaded():
    """Run sync automatically when Anki starts (if configured)."""
    config = get_config()
    if config.get("auto_sync_on_startup") and config.get("api_token"):
        run_sync()

        # Optionally trigger AnkiWeb sync after our sync
        if config.get("trigger_ankiweb_sync_after"):
            mw.onSync()


# Add menu item
action = QAction("Anki Translator: Sync Now", mw)
action.triggered.connect(run_sync)
mw.form.menuTools.addAction(action)

# Auto-sync on profile load
gui_hooks.profile_did_open.append(on_profile_loaded)
