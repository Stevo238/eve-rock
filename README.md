# EVE Rock – Mining Tracker

A PyQt6 desktop application for tracking EVE Online mining activity across
multiple characters, with persistent SQLite history and corp moon-mining support.

---

## Features

| Feature | Details |
|---|---|
| **Multi-account** | Add as many characters as you like; each authenticates independently via EVE SSO |
| **Multi-select characters** | Sidebar supports Ctrl+click / Shift+click to filter any combination of characters |
| **Character Mining** | Full ledger from ESI – date, solar system, ore type, group, quantity, Est. m³, Est. ISK |
| **Time gates** | Period dropdown (7 / 30 / 90 / 180 days / All time / Custom range) on every tab |
| **Moon Mining** | Corp moon-drill observer data (requires Director or Accountant corp role) |
| **Moon character panel** | Vertical left-panel character filter with multi-select, mirroring the main sidebar |
| **Moon tax** | Configurable tax % (default 15%) calculates per-row and total tax column |
| **Moon totals row** | Bold gold TOTALS footer across Quantity, Est. m³, Est. ISK and Tax |
| **ISK Estimates** | Live average market prices from ESI, applied to all quantities |
| **Volume totals** | m³ calculated per ore type using ESI type data (cached locally) |
| **Group names** | Ore/ice group names resolved from ESI and cached; auto back-filled at startup |
| **History** | SQLite at `~/.eve_rock_data.db` accumulates data beyond ESI's 30-day window |
| **Moon cycle detection** | Archives old moon-cycle records automatically when quantities reset |
| **Summary tab** | Per-character and per-ore-type breakdowns with filterable time periods |
| **Export CSV** | Export button on each tab — single CSV for Mining/Moon, dual CSV for Summary |
| **Performance** | `setUpdatesEnabled` batching prevents UI hang on large datasets |

---

## Quick Start (Development)

```bash
# 1. Clone
git clone https://github.com/Stevo238/eve-rock.git
cd eve-rock

# 2. Create a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

On first launch you'll be prompted for your **EVE Developer Application Client ID**
if `BAKED_CLIENT_ID` in `main.py` is empty.

---

## Create an EVE Developer Application

1. Go to <https://developers.eveonline.com/> and log in.
2. Click **Manage Applications → Create New Application**.
3. Set:
   - **Callback URL**: `http://localhost:45679/callback`
   - **Scopes**:
     - `esi-industry.read_character_mining.v1`
     - `esi-industry.read_corporation_mining.v1`
     - `esi-universe.read_structures.v1`
4. Copy the **Client ID** (not the secret – PKCE doesn't need it).

---

## Distributing to Corp Mates

1. Paste your Client ID into `BAKED_CLIENT_ID` in `main.py`.
2. Install PyInstaller: `pip install pyinstaller`
3. Build: `pyinstaller eve_rock.spec`
4. Share `dist/EVERock.exe` – no Python installation required.

Each corp mate logs in with **their own EVE account**. Tokens are saved locally
per user in `~/.eve_rock_tokens.json`. History accumulates in `~/.eve_rock_data.db`.

---

## Tabs Overview

### ⛏ Character Mining
- Filterable by period (preset or custom date range)
- Multi-select characters in the sidebar to compare accounts
- Columns: Character, Date, Solar System, Ore/Ice Type, Group, Quantity, Est. m³, Est. ISK
- Summary pills: rows, total units, volume, ISK, mining days, ore types
- Export CSV button

### 🌙 Moon Mining
- Left panel: multi-select character filter (Ctrl+click / Shift+click)
- Filter bar: Period, Observer, Tax %
- Columns: Observer/Refinery, Character, Ore/Ice Type, Group, Quantity, Est. m³, Est. ISK, Tax, Last Updated
- Bold gold **TOTALS** footer row
- Summary pills include Tax amount
- Export CSV button

### 📊 Summary
- Period filter with custom date range
- Two side-by-side tables: By Character and By Ore/Ice Type
- Export writes two CSVs automatically (`_by_character` and `_by_type`)

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
  cycle to the `moon_mining_history` table, so historical data is preserved.
- Click **Fetch Moon Mining** on the Moon Mining tab to pull the latest data.

---

## ESI Scopes Requested

| Scope | Used For |
|---|---|
| `esi-industry.read_character_mining.v1` | Individual character mining ledger |
| `esi-industry.read_corporation_mining.v1` | Corp moon-drill observer data |
| `esi-universe.read_structures.v1` | Structure/refinery name resolution |

---

## Requirements

- Python 3.10+
- PyQt6 >= 6.6.0
- requests >= 2.31.0

