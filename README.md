# EVE Rock – Mining Tracker

A PyQt6 desktop application for tracking EVE Online mining activity across
multiple characters, with persistent SQLite history and corp moon-mining support.

---

## Features

| Feature | Details |
|---|---|
| **Multi-account** | Add as many characters as you like; each authenticates independently via EVE SSO |
| **Character Mining** | Full 30-day ledger from ESI, enriched with solar-system names, ore-type names and volumes |
| **Moon Mining** | Corp moon-drill observer data (requires Director or Accountant corp role) |
| **ISK Estimates** | Live average market prices from ESI, applied to all quantities |
| **Volume totals** | m³ calculated per ore type using ESI type data (cached locally) |
| **History** | SQLite database at `~/.eve_rock_data.db` accumulates data beyond ESI's 30-day window |
| **Moon cycle detection** | Automatically archives old moon-cycle records when quantities reset (moon re-pop) |
| Summary tab | Per-character and per-ore-type breakdowns with filterable time periods |

---

## Quick Start (Development)

```bash
# 1. Clone / copy files into a folder
# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

On first launch you'll be prompted for your **EVE Developer Application Client ID**.

---

## Create an EVE Developer Application

1. Go to <https://developers.eveonline.com/> and log in.
2. Click **Manage Applications → Create New Application**.
3. Set:
   - **Callback URL**: `http://localhost:45679/callback`
   - **Scopes**:
     - `esi-industry.read_character_mining.v1`
     - `esi-industry.read_corporation_mining.v1`
4. Copy the **Client ID** (not the secret – PKCE doesn't need it).

---

## Distributing to Corp Mates

1. Paste your Client ID into `BAKED_CLIENT_ID` in `main.py`.
2. Install PyInstaller: `pip install pyinstaller`
3. Build: `pyinstaller eve_rock.spec`
4. Share `dist/EVERock.exe` – no Python installation required.

Each corp mate logs in with **their own EVE account**.  Tokens are saved locally
per user in `~/.eve_rock_tokens.json`.  History accumulates in `~/.eve_rock_data.db`.

---

## Stored Files

| File | Purpose |
|---|---|
| `~/.eve_rock_tokens.json` | OAuth2 tokens, one entry per character |
| `~/.eve_rock_data.db` | SQLite history (mining ledger, moon mining, type cache) |

---

## Moon Mining Notes

- Requires one character with **Director** or **Accountant** role.
- ESI returns cumulative quantities per character per ore type **since the last moon
  re-pop** (when the Athanor / Tatara drilled out the chunk and a new one was loaded).
- EVE Rock detects when quantities reset and automatically archives the previous
  cycle to the `moon_mining_history` table, so you don't lose historical data.
- Click **Fetch Moon Mining** on the Moon Mining tab to pull the latest data.

---

## ESI Scopes Requested

| Scope | Used For |
|---|---|
| `esi-industry.read_character_mining.v1` | Individual character mining ledger |
| `esi-industry.read_corporation_mining.v1` | Corp moon-drill observer data |
