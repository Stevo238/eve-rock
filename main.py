"""
EVE Rock – Mining Tracker
Entry point.

DISTRIBUTION NOTE
-----------------
Set BAKED_CLIENT_ID to your EVE developer application Client ID before
building the exe with PyInstaller.  This is not a secret – PKCE apps are
designed to share a public Client ID.  All corp-mates use the same ID and
each person logs in with their own EVE account.

Create your application at  https://developers.eveonline.com/
    • Callback URL : http://localhost:45679/callback
    • Scopes (ESI > industry):
        esi-industry.read_character_mining.v1
        esi-industry.read_corporation_mining.v1
"""

import sys

from PyQt6.QtWidgets import QApplication, QInputDialog, QMessageBox

from ui import MainWindow, STYLESHEET

# ── Paste your Client ID here before building the exe ──────────────────────────
BAKED_CLIENT_ID = ""   # ← paste your Client ID before running / building
# ───────────────────────────────────────────────────────────────────────────────


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("EVE Rock")
    app.setStyleSheet(STYLESHEET)

    client_id = BAKED_CLIENT_ID.strip()

    if not client_id:
        # Developer fallback – interactive prompt so the app still works in
        # development without needing to rebuild just to change the Client ID.
        cid, ok = QInputDialog.getText(
            None,
            "EVE Rock – Setup",
            (
                "Enter your EVE Developer Application Client ID:\n\n"
                "  1. Go to  https://developers.eveonline.com/\n"
                "  2. Create an application with:\n"
                "       Callback:  http://localhost:45679/callback\n"
                "       Scopes:    esi-industry.read_character_mining.v1\n"
                "                  esi-industry.read_corporation_mining.v1\n"
                "  3. Paste your Client ID below."
            ),
        )
        if not ok or not cid.strip():
            QMessageBox.warning(None, "No Client ID",
                                "A Client ID is required to use EVE Rock.")
            sys.exit(1)
        client_id = cid.strip()

    window = MainWindow(client_id)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
