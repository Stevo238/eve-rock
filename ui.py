"""
EVE Rock – PyQt6 GUI.

Layout
------
Left sidebar  – character list (add / remove / sync per character)
Right content – QTabWidget with three tabs:
    ⛏  Character Mining  – full ledger, filterable by character & period
    🌙  Moon Mining       – corp observer data (requires director/accountant role)
    📊  Summary          – aggregate stats by character and by ore type
"""

import sys
from datetime import datetime, timedelta

from PyQt6.QtCore    import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui     import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSizePolicy, QSplitter, QStatusBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import auth
import esi
from database import Database

# ── Colour palette (same dark-space theme as EVE Gas Man) ─────────────────────
DARK_BG      = "#0d1117"
PANEL_BG     = "#161b22"
BORDER       = "#30363d"
TEXT_PRIMARY = "#e6edf3"
TEXT_SEC     = "#8b949e"
ACCENT_BLUE  = "#58a6ff"
ACCENT_GREEN = "#3fb950"
WARN_YELLOW  = "#d29922"
DANGER_RED   = "#f85149"
HEADER_BG    = "#21262d"
ORE_GOLD     = "#e3a62f"
ICE_CYAN     = "#3ecfcf"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}
QSplitter::handle {{
    background-color: {BORDER};
    width: 1px;
}}
QTableWidget {{
    background-color: {PANEL_BG};
    gridline-color: {BORDER};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: #1f6feb;
    alternate-background-color: #101820;
}}
QTableWidget::item {{
    padding: 5px 8px;
    border: none;
}}
QHeaderView::section {{
    background-color: {HEADER_BG};
    color: {TEXT_SEC};
    font-weight: bold;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    letter-spacing: 0.5px;
}}
QHeaderView::section:hover {{
    background-color: #2d333b;
    color: {TEXT_PRIMARY};
}}
QPushButton {{
    background-color: #238636;
    color: white;
    border: 1px solid #2ea043;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton:hover  {{ background-color: #2ea043; }}
QPushButton:pressed {{ background-color: #1a7f37; }}
QPushButton:disabled {{ background-color: #21262d; color: {TEXT_SEC}; border-color: {BORDER}; }}
QPushButton#danger_btn {{
    background-color: transparent;
    color: {TEXT_SEC};
    border: 1px solid {BORDER};
}}
QPushButton#danger_btn:hover {{ color: {DANGER_RED}; border-color: {DANGER_RED}; }}
QPushButton#blue_btn {{
    background-color: #1f6feb;
    border-color: #388bfd;
}}
QPushButton#blue_btn:hover {{ background-color: #388bfd; }}
QLabel#title_label {{
    font-size: 22px;
    font-weight: 700;
    color: {ORE_GOLD};
    letter-spacing: 1px;
}}
QLabel#section_label {{
    color: {TEXT_SEC};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QStatusBar {{
    background-color: {PANEL_BG};
    color: {TEXT_SEC};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 0 6px 6px 6px;
    background-color: {PANEL_BG};
}}
QTabBar::tab {{
    background-color: {DARK_BG};
    color: {TEXT_SEC};
    padding: 8px 20px;
    border: 1px solid {BORDER};
    border-bottom: none;
    margin-right: 2px;
    border-radius: 6px 6px 0 0;
    min-width: 140px;
}}
QTabBar::tab:selected {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ background-color: {HEADER_BG}; color: {TEXT_PRIMARY}; }}
QListWidget {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {BORDER};
    color: {TEXT_PRIMARY};
}}
QListWidget::item:selected {{
    background-color: #1f6feb;
    color: white;
}}
QListWidget::item:hover:!selected {{ background-color: {HEADER_BG}; }}
QComboBox {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 140px;
}}
QComboBox:focus {{ border-color: {ACCENT_BLUE}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: #1f6feb;
}}
QLineEdit {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
}}
QLineEdit:focus {{ border-color: {ACCENT_BLUE}; }}
QMenu {{
    background-color: {PANEL_BG};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 20px; border-radius: 3px; }}
QMenu::item:selected {{ background-color: #1f6feb; }}
QDialog {{ background-color: {DARK_BG}; }}
"""

# ── Helpers ────────────────────────────────────────────────────────────────────

_PERIOD_OPTIONS = [
    ("Last 7 days",   7),
    ("Last 30 days",  30),
    ("Last 90 days",  90),
    ("Last 180 days", 180),
    ("All time",      None),
]


def _period_dates(days: int | None) -> tuple[str | None, str | None]:
    """Return (start_date_str, end_date_str) or (None, None) for all time."""
    if days is None:
        return None, None
    start = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    return start, None


def _fmt_quantity(n: int) -> str:
    return f"{n:,}"


def _fmt_isk(v: float) -> str:
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f} B ISK"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f} M ISK"
    return f"{v:,.0f} ISK"


def _fmt_m3(v: float) -> str:
    if v >= 1_000_000:
        return f"{v / 1_000_000:.2f} Mm³"
    if v >= 1_000:
        return f"{v / 1_000:.2f} km³"
    return f"{v:,.2f} m³"


def _pill(text: str, color: str = TEXT_SEC) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {color}; font-size: 12px;"
        f"background: {DARK_BG}; border: 1px solid {BORDER};"
        f"border-radius: 4px; padding: 3px 10px;"
    )
    return lbl


def _setup_table(tbl: QTableWidget) -> None:
    tbl.verticalHeader().setVisible(False)
    tbl.verticalHeader().setDefaultSectionSize(32)
    tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tbl.setAlternatingRowColors(True)
    tbl.setShowGrid(False)
    tbl.setSortingEnabled(True)


def _cell(text: str, align=Qt.AlignmentFlag.AlignLeft,
          color: str | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    if color:
        item.setForeground(QColor(color))
    return item


def _num_cell(value: float, display: str) -> QTableWidgetItem:
    """Numeric cell that sorts by numeric value, displays formatted string."""
    item = QTableWidgetItem()
    item.setData(Qt.ItemDataRole.DisplayRole, display)
    item.setData(Qt.ItemDataRole.UserRole,    value)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item


# ── Background workers ─────────────────────────────────────────────────────────

class AddCharacterWorker(QThread):
    """Opens EVE SSO browser flow and adds a new character."""

    success = pyqtSignal(int, str, int, str)   # char_id, name, corp_id, corp_name
    failed  = pyqtSignal(str)

    def __init__(self, client_id: str):
        super().__init__()
        self._client_id = client_id

    def run(self):
        try:
            result = auth.start_add_character(self._client_id)
            if not result:
                self.failed.emit("Login failed or timed out.  Please try again.")
                return
            char_id, token = result
            corp_id        = token.get("corporation_id") or 0
            char_name      = token.get("character_name", f"Char {char_id}")
            corp_name      = esi.get_corporation_name(corp_id, token["access_token"]) if corp_id else ""
            self.success.emit(char_id, char_name, corp_id, corp_name)
        except Exception as exc:
            self.failed.emit(str(exc))


class SyncWorker(QThread):
    """Fetches mining ledgers for one or all characters and saves to the DB."""

    progress    = pyqtSignal(str)
    char_synced = pyqtSignal(int, str, str)   # char_id, char_name, corp_name
    finished    = pyqtSignal()
    error       = pyqtSignal(str)

    def __init__(self, client_id: str, tokens: dict, db: Database,
                 char_ids: list[int] | None = None):
        super().__init__()
        self._client_id = client_id
        self._tokens    = dict(tokens)          # copy to avoid race conditions
        self._db        = db
        self._char_ids  = char_ids              # None → sync all

    def run(self):
        prices = {}
        try:
            prices = esi.get_market_prices()
        except Exception:
            pass

        for char_id_str, token in self._tokens.items():
            char_id = int(char_id_str)
            if self._char_ids and char_id not in self._char_ids:
                continue

            char_name = token.get("character_name", f"Char {char_id}")
            self.progress.emit(f"Syncing {char_name}…")

            try:
                token = auth.get_valid_token(self._client_id, char_id, token)
                if not token:
                    self.error.emit(f"Session expired for {char_name} – please re-authenticate.")
                    continue

                access = token["access_token"]

                # ── Fetch ESI mining ledger ──────────────────────────────────
                raw_entries = esi.get_character_mining(char_id, access)

                if raw_entries:
                    # Collect IDs that need name resolution
                    type_ids   = list({e["type_id"]          for e in raw_entries})
                    system_ids = list({e["solar_system_id"]  for e in raw_entries})
                    names      = esi.resolve_names(system_ids + type_ids, access)

                    # Fetch type info for unknown types (volume, group)
                    known_types = self._db.get_known_type_ids()
                    new_type_ids = [t for t in type_ids if t not in known_types]
                    if new_type_ids:
                        self.progress.emit(f"{char_name}: fetching {len(new_type_ids)} ore type(s)…")
                        type_infos = esi.get_types_batch(new_type_ids, access)
                        for tid, info in type_infos.items():
                            self._db.save_type_info(
                                tid,
                                info.get("name", names.get(tid, f"Type {tid}")),
                                info.get("volume", 0.0),
                                info.get("group_id"),
                            )

                    # Enrich entries with resolved names
                    enriched = []
                    for e in raw_entries:
                        tid = e["type_id"]
                        sid = e["solar_system_id"]
                        enriched.append({
                            "date":             str(e.get("date", "")),
                            "solar_system_id":  sid,
                            "solar_system_name": names.get(sid, f"System {sid}"),
                            "type_id":          tid,
                            "type_name":        names.get(tid, f"Type {tid}"),
                            "quantity":         e.get("quantity", 0),
                        })
                    self._db.save_mining_entries(char_id, enriched)

                # ── Update character record ──────────────────────────────────
                corp_id   = token.get("corporation_id") or 0
                corp_name = esi.get_corporation_name(corp_id, access) if corp_id else ""
                self._db.save_character(char_id, char_name, corp_id, corp_name)
                self.char_synced.emit(char_id, char_name, corp_name)

            except Exception as exc:
                self.error.emit(f"{char_name}: {exc}")

        self.finished.emit()


class MoonWorker(QThread):
    """Fetches corp moon-mining data for a single character's corporation."""

    progress      = pyqtSignal(str)
    finished      = pyqtSignal(list)   # list of observer dicts
    error         = pyqtSignal(str)
    no_permission = pyqtSignal()

    def __init__(self, client_id: str, char_id: int, token: dict,
                 corp_id: int, db: Database):
        super().__init__()
        self._client_id = client_id
        self._char_id   = char_id
        self._token     = token
        self._corp_id   = corp_id
        self._db        = db

    def run(self):
        try:
            token = auth.get_valid_token(self._client_id, self._char_id, self._token)
            if not token:
                self.error.emit("Session expired – please re-authenticate.")
                return
            access = token["access_token"]

            self.progress.emit("Fetching moon-mining observers…")
            observers = esi.get_corp_mining_observers(self._corp_id, access)

            if observers is None:
                self.no_permission.emit()
                return

            result = []
            # Collect all type IDs across observers for batch fetch
            all_type_ids_needed: set[int] = set()

            for obs in observers:
                obs_id   = obs["observer_id"]
                obs_type = obs.get("observer_type", "structure")
                obs_name = (
                    esi.get_structure_name(obs_id, access)
                    if obs_type == "structure"
                    else f"{obs_type} {obs_id}"
                )
                self.progress.emit(f"Fetching mining at {obs_name}…")

                entries  = esi.get_observer_mining(self._corp_id, obs_id, access)
                char_ids = list({e["character_id"] for e in entries})
                type_ids = list({e["type_id"]       for e in entries})
                names    = esi.resolve_names(char_ids + type_ids, access)

                # Queue unknown types for volume fetch
                known = self._db.get_known_type_ids()
                all_type_ids_needed.update(t for t in type_ids if t not in known)

                enriched = [
                    {
                        "character_id":     e["character_id"],
                        "character_name":   names.get(e["character_id"], f"Char {e['character_id']}"),
                        "recorded_corp_id": e.get("recorded_corporation_id"),
                        "type_id":          e["type_id"],
                        "type_name":        names.get(e["type_id"], f"Type {e['type_id']}"),
                        "quantity":         e.get("quantity", 0),
                        "last_updated":     e.get("last_updated", ""),
                    }
                    for e in entries
                ]
                self._db.save_moon_mining(obs_id, obs_name, enriched)
                result.append({"observer_id": obs_id, "observer_name": obs_name})

            # Batch-fetch unknown type volumes
            if all_type_ids_needed:
                self.progress.emit(f"Fetching {len(all_type_ids_needed)} ore type(s)…")
                type_infos = esi.get_types_batch(list(all_type_ids_needed), access)
                for tid, info in type_infos.items():
                    self._db.save_type_info(tid, info.get("name", ""), info.get("volume", 0.0), info.get("group_id"))

            self.finished.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))


# ── Main window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, client_id: str):
        super().__init__()
        self._client_id  = client_id
        self._db         = Database()
        self._tokens     = auth.load_all_tokens()   # {str(char_id): token_dict}
        self._sync_worker: SyncWorker | None    = None
        self._moon_worker: MoonWorker | None    = None
        self._add_worker: AddCharacterWorker | None = None
        self._market_prices: dict[int, float]   = {}

        self.setWindowTitle("EVE Rock – Mining Tracker")
        self.setMinimumSize(1200, 680)
        self.resize(1500, 800)
        self._build_ui()
        self._load_existing_characters()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 1280])
        root.addWidget(splitter)

        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)
        self._status_lbl = QLabel("Add characters via the sidebar to get started.")
        sb.addWidget(self._status_lbl, 1)
        self._ts_lbl = QLabel("")
        sb.addPermanentWidget(self._ts_lbl)

    # ── Sidebar ────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(220)
        panel.setStyleSheet(f"background-color: {PANEL_BG}; border-right: 1px solid {BORDER};")

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 14, 10, 10)
        lay.setSpacing(8)

        hdr = QLabel("CHARACTERS")
        hdr.setObjectName("section_label")
        lay.addWidget(hdr)

        self._char_list = QListWidget()
        self._char_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._char_list.customContextMenuRequested.connect(self._on_char_context_menu)
        self._char_list.currentItemChanged.connect(self._on_char_selected)
        lay.addWidget(self._char_list)

        # "All Characters" entry
        all_item = QListWidgetItem("⬛  All Characters")
        all_item.setData(Qt.ItemDataRole.UserRole, None)
        f = all_item.font(); f.setBold(True); all_item.setFont(f)
        self._char_list.addItem(all_item)
        self._char_list.setCurrentItem(all_item)

        self._add_btn = QPushButton("＋  Add Character")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.clicked.connect(self._on_add_character)
        lay.addWidget(self._add_btn)

        self._sync_all_btn = QPushButton("↺  Sync All")
        self._sync_all_btn.setObjectName("blue_btn")
        self._sync_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_all_btn.clicked.connect(self._on_sync_all)
        lay.addWidget(self._sync_all_btn)

        return panel

    # ── Right panel ────────────────────────────────────────────────────

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        lay   = QVBoxLayout(panel)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(10)

        # Header row
        hdr = QHBoxLayout()
        title = QLabel("EVE Rock")
        title.setObjectName("title_label")
        sub   = QLabel("Mining Tracker")
        sub.setStyleSheet(f"color: {TEXT_SEC}; font-size: 13px; margin-top: 6px;")
        hdr.addWidget(title)
        hdr.addWidget(sub)
        hdr.addStretch()
        lay.addLayout(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {BORDER}; max-height: 1px;")
        lay.addWidget(sep)

        # Tabs
        self._tabs = QTabWidget()
        self._tab_mining  = self._build_tab_mining()
        self._tab_moon    = self._build_tab_moon()
        self._tab_summary = self._build_tab_summary()
        self._tabs.addTab(self._tab_mining,  "⛏  Character Mining")
        self._tabs.addTab(self._tab_moon,    "🌙  Moon Mining")
        self._tabs.addTab(self._tab_summary, "📊  Summary")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self._tabs)
        return panel

    # ── Tab: Character Mining ──────────────────────────────────────────

    def _build_tab_mining(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # Filter bar
        fbar = QHBoxLayout(); fbar.setSpacing(12)
        fbar.addWidget(QLabel("Period:"))
        self._mining_period = QComboBox()
        for label, _ in _PERIOD_OPTIONS:
            self._mining_period.addItem(label)
        self._mining_period.setCurrentIndex(1)   # 30 days default
        self._mining_period.currentIndexChanged.connect(self._refresh_mining_tab)
        fbar.addWidget(self._mining_period)

        fbar.addStretch()

        sync_btn = QPushButton("↺  Refresh")
        sync_btn.setObjectName("blue_btn")
        sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sync_btn.clicked.connect(self._on_sync_all)
        fbar.addWidget(sync_btn)
        lay.addLayout(fbar)

        # Summary pills
        prow = QHBoxLayout(); prow.setSpacing(10)
        self._mp_rows    = _pill("Rows: —")
        self._mp_total   = _pill("Total units: —")
        self._mp_m3      = _pill("Volume: —")
        self._mp_isk     = _pill("Est. ISK: —")
        self._mp_days    = _pill("Mining days: —")
        self._mp_types   = _pill("Ore types: —")
        for p in (self._mp_rows, self._mp_total, self._mp_m3, self._mp_isk,
                  self._mp_days, self._mp_types):
            prow.addWidget(p)
        prow.addStretch()
        lay.addLayout(prow)

        # Table
        self._mining_table = QTableWidget()
        self._mining_table.setColumnCount(9)
        self._mining_table.setHorizontalHeaderLabels([
            "Character", "Date", "Solar System", "Ore / Ice Type",
            "Group", "Quantity", "Est. m³", "Est. ISK", "Ref"
        ])
        _setup_table(self._mining_table)
        hv = self._mining_table.horizontalHeader()
        for col, mode in [
            (0, QHeaderView.ResizeMode.Interactive),
            (1, QHeaderView.ResizeMode.ResizeToContents),
            (2, QHeaderView.ResizeMode.ResizeToContents),
            (3, QHeaderView.ResizeMode.Stretch),
            (4, QHeaderView.ResizeMode.ResizeToContents),
            (5, QHeaderView.ResizeMode.ResizeToContents),
            (6, QHeaderView.ResizeMode.ResizeToContents),
            (7, QHeaderView.ResizeMode.ResizeToContents),
            (8, QHeaderView.ResizeMode.ResizeToContents),
        ]:
            hv.setSectionResizeMode(col, mode)
        self._mining_table.setColumnWidth(0, 160)
        lay.addWidget(self._mining_table)
        return w

    # ── Tab: Moon Mining ──────────────────────────────────────────────

    def _build_tab_moon(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # Info banner
        info = QLabel(
            "ℹ  Moon mining data requires the primary character to hold a "
            "Director or Accountant role in the corporation."
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"color: {WARN_YELLOW}; font-size: 12px;"
            f"background: #2d2700; border: 1px solid {WARN_YELLOW};"
            f"border-radius: 4px; padding: 6px 10px;"
        )
        lay.addWidget(info)

        # Filter bar
        fbar = QHBoxLayout(); fbar.setSpacing(12)
        fbar.addWidget(QLabel("Observer:"))
        self._moon_observer = QComboBox()
        self._moon_observer.addItem("All Observers", None)
        self._moon_observer.currentIndexChanged.connect(self._refresh_moon_tab)
        fbar.addWidget(self._moon_observer)

        fbar.addWidget(QLabel("Character:"))
        self._moon_char_combo = QComboBox()
        self._moon_char_combo.addItem("Any character", None)
        self._moon_char_combo.currentIndexChanged.connect(self._refresh_moon_tab)
        fbar.addWidget(self._moon_char_combo)

        fbar.addStretch()

        self._moon_sync_btn = QPushButton("↺  Fetch Moon Mining")
        self._moon_sync_btn.setObjectName("blue_btn")
        self._moon_sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._moon_sync_btn.clicked.connect(self._on_sync_moon)
        fbar.addWidget(self._moon_sync_btn)
        lay.addLayout(fbar)

        # Summary pills
        prow = QHBoxLayout(); prow.setSpacing(10)
        self._moonp_chars  = _pill("Characters: —")
        self._moonp_total  = _pill("Total units: —")
        self._moonp_m3     = _pill("Volume: —")
        self._moonp_isk    = _pill("Est. ISK: —")
        self._moonp_types  = _pill("Ore types: —")
        for p in (self._moonp_chars, self._moonp_total, self._moonp_m3,
                  self._moonp_isk, self._moonp_types):
            prow.addWidget(p)
        prow.addStretch()
        lay.addLayout(prow)

        # Table
        self._moon_table = QTableWidget()
        self._moon_table.setColumnCount(7)
        self._moon_table.setHorizontalHeaderLabels([
            "Observer / Refinery", "Character", "Ore / Ice Type",
            "Group", "Quantity", "Est. m³", "Last Updated"
        ])
        _setup_table(self._moon_table)
        hv = self._moon_table.horizontalHeader()
        for col, mode in [
            (0, QHeaderView.ResizeMode.Interactive),
            (1, QHeaderView.ResizeMode.ResizeToContents),
            (2, QHeaderView.ResizeMode.Stretch),
            (3, QHeaderView.ResizeMode.ResizeToContents),
            (4, QHeaderView.ResizeMode.ResizeToContents),
            (5, QHeaderView.ResizeMode.ResizeToContents),
            (6, QHeaderView.ResizeMode.ResizeToContents),
        ]:
            hv.setSectionResizeMode(col, mode)
        self._moon_table.setColumnWidth(0, 220)
        lay.addWidget(self._moon_table)
        return w

    # ── Tab: Summary ──────────────────────────────────────────────────

    def _build_tab_summary(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(12)

        # Period filter
        fbar = QHBoxLayout(); fbar.setSpacing(12)
        fbar.addWidget(QLabel("Period:"))
        self._summary_period = QComboBox()
        for label, _ in _PERIOD_OPTIONS:
            self._summary_period.addItem(label)
        self._summary_period.setCurrentIndex(1)
        self._summary_period.currentIndexChanged.connect(self._refresh_summary_tab)
        fbar.addWidget(self._summary_period)
        fbar.addStretch()
        lay.addLayout(fbar)

        # Two side-by-side tables
        tables_row = QHBoxLayout(); tables_row.setSpacing(12)

        # By character
        left = QVBoxLayout()
        lbl = QLabel("BY CHARACTER")
        lbl.setObjectName("section_label")
        left.addWidget(lbl)
        self._sum_char_table = QTableWidget()
        self._sum_char_table.setColumnCount(5)
        self._sum_char_table.setHorizontalHeaderLabels([
            "Character", "Corporation", "Total Units", "Active Days", "Ore Types"
        ])
        _setup_table(self._sum_char_table)
        hv = self._sum_char_table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        hv.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        for c in (2, 3, 4):
            hv.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._sum_char_table.setColumnWidth(0, 160)
        self._sum_char_table.setColumnWidth(1, 180)
        left.addWidget(self._sum_char_table)
        tables_row.addLayout(left)

        # By ore type
        right = QVBoxLayout()
        lbl2 = QLabel("BY ORE / ICE TYPE")
        lbl2.setObjectName("section_label")
        right.addWidget(lbl2)
        self._sum_type_table = QTableWidget()
        self._sum_type_table.setColumnCount(5)
        self._sum_type_table.setHorizontalHeaderLabels([
            "Ore / Ice Type", "Group", "Total Units", "Est. m³", "Est. ISK"
        ])
        _setup_table(self._sum_type_table)
        hv2 = self._sum_type_table.horizontalHeader()
        hv2.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hv2.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for c in (2, 3, 4):
            hv2.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        right.addWidget(self._sum_type_table)
        tables_row.addLayout(right)

        lay.addLayout(tables_row, 1)
        return w

    # ------------------------------------------------------------------
    # Character sidebar management
    # ------------------------------------------------------------------

    def _load_existing_characters(self):
        """Populate sidebar from the saved token file + local DB."""
        for char_id_str, token in self._tokens.items():
            char_id   = int(char_id_str)
            char_name = token.get("character_name", f"Char {char_id}")
            # Try to enrich from DB
            row = self._db.get_character(char_id)
            corp_name = row["corporation_name"] if row else ""
            self._add_char_to_list(char_id, char_name, corp_name)

    def _add_char_to_list(self, char_id: int, char_name: str, corp_name: str):
        # Remove if already present (re-auth case)
        for i in range(self._char_list.count()):
            item = self._char_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == char_id:
                self._char_list.takeItem(i)
                break

        item = QListWidgetItem()
        item.setText(f"●  {char_name}\n    {corp_name or 'Unknown Corp'}")
        item.setData(Qt.ItemDataRole.UserRole, char_id)
        item.setToolTip(f"Character ID: {char_id}\n{corp_name}")
        self._char_list.addItem(item)

    def _update_char_item(self, char_id: int, char_name: str, corp_name: str):
        for i in range(self._char_list.count()):
            item = self._char_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == char_id:
                item.setText(f"●  {char_name}\n    {corp_name or 'Unknown Corp'}")
                return
        self._add_char_to_list(char_id, char_name, corp_name)

    def _selected_char_id(self) -> int | None:
        item = self._char_list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)  # None = "All"

    def _on_char_selected(self):
        self._refresh_current_tab()

    def _on_char_context_menu(self, pos):
        item = self._char_list.itemAt(pos)
        if not item:
            return
        char_id = item.data(Qt.ItemDataRole.UserRole)
        if char_id is None:
            return   # "All Characters" row has no context menu
        menu = QMenu(self)
        sync_act   = menu.addAction("↺  Sync this character")
        reauth_act = menu.addAction("🔑  Re-authenticate")
        menu.addSeparator()
        remove_act = menu.addAction("✕  Remove character")
        action = menu.exec(self._char_list.mapToGlobal(pos))
        if action == sync_act:
            self._on_sync_chars([char_id])
        elif action == reauth_act:
            self._on_add_character()
        elif action == remove_act:
            self._on_remove_character(char_id)

    def _on_remove_character(self, char_id: int):
        row = self._db.get_character(char_id)
        name = row["character_name"] if row else f"Char {char_id}"
        reply = QMessageBox.question(
            self, "Remove Character",
            f"Remove {name}?\n\nMining history will be kept in the local database.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        auth.remove_character(char_id)
        self._tokens.pop(str(char_id), None)
        for i in range(self._char_list.count()):
            item = self._char_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == char_id:
                self._char_list.takeItem(i)
                break
        if not self._char_list.currentItem():
            self._char_list.setCurrentRow(0)
        self._refresh_current_tab()

    # ------------------------------------------------------------------
    # Add / sync workers
    # ------------------------------------------------------------------

    def _on_add_character(self):
        if self._add_worker and self._add_worker.isRunning():
            return
        self._add_btn.setEnabled(False)
        self._set_status("Opening browser for EVE SSO login…")
        self._add_worker = AddCharacterWorker(self._client_id)
        self._add_worker.success.connect(self._on_add_success, Qt.ConnectionType.QueuedConnection)
        self._add_worker.failed.connect( self._on_add_failed,  Qt.ConnectionType.QueuedConnection)
        self._add_worker.start()

    def _on_add_success(self, char_id: int, char_name: str, corp_id: int, corp_name: str):
        self._add_btn.setEnabled(True)
        # Re-load tokens from file (worker saved them)
        self._tokens = auth.load_all_tokens()
        self._db.save_character(char_id, char_name, corp_id, corp_name)
        self._add_char_to_list(char_id, char_name, corp_name)
        self._set_status(f"Added {char_name} – syncing mining data…")
        self._on_sync_chars([char_id])

    def _on_add_failed(self, msg: str):
        self._add_btn.setEnabled(True)
        self._set_status(f"Login failed: {msg}")

    def _on_sync_all(self):
        self._on_sync_chars(None)

    def _on_sync_chars(self, char_ids: list[int] | None):
        if self._sync_worker and self._sync_worker.isRunning():
            return
        if not self._tokens:
            self._set_status("No characters added yet.")
            return
        self._sync_all_btn.setEnabled(False)
        self._sync_worker = SyncWorker(self._client_id, self._tokens, self._db, char_ids)
        self._sync_worker.progress.connect(   self._set_status,            Qt.ConnectionType.QueuedConnection)
        self._sync_worker.char_synced.connect(self._on_char_synced,        Qt.ConnectionType.QueuedConnection)
        self._sync_worker.finished.connect(   self._on_sync_finished,      Qt.ConnectionType.QueuedConnection)
        self._sync_worker.error.connect(      self._on_sync_error,         Qt.ConnectionType.QueuedConnection)
        self._sync_worker.start()

    def _on_char_synced(self, char_id: int, char_name: str, corp_name: str):
        self._update_char_item(char_id, char_name, corp_name)

    def _on_sync_finished(self):
        self._sync_all_btn.setEnabled(True)
        self._tokens = auth.load_all_tokens()   # pick up any refreshed tokens
        self._ts_lbl.setText(f"Last sync: {datetime.now().strftime('%H:%M:%S')}")
        self._set_status("Sync complete.")
        try:
            self._market_prices = esi.get_market_prices()
        except Exception:
            pass
        self._refresh_current_tab()

    def _on_sync_error(self, msg: str):
        self._set_status(f"⚠  {msg}")

    # ── Moon sync ──────────────────────────────────────────────────────

    def _on_sync_moon(self):
        if self._moon_worker and self._moon_worker.isRunning():
            return
        # Use selected character, or the first one that has a corp_id
        sel_id = self._selected_char_id()
        if sel_id is None:
            # Try the first character in the list
            for i in range(1, self._char_list.count()):
                item = self._char_list.item(i)
                if item:
                    sel_id = item.data(Qt.ItemDataRole.UserRole)
                    break
        if sel_id is None:
            self._set_status("Add at least one character first.")
            return
        token = self._tokens.get(str(sel_id))
        if not token:
            self._set_status("No token for selected character – please re-authenticate.")
            return
        corp_id = token.get("corporation_id") or 0
        if not corp_id:
            self._set_status("Could not determine corporation ID.")
            return

        self._moon_sync_btn.setEnabled(False)
        self._moon_worker = MoonWorker(self._client_id, sel_id, token, corp_id, self._db)
        self._moon_worker.progress.connect(     self._set_status,       Qt.ConnectionType.QueuedConnection)
        self._moon_worker.finished.connect(     self._on_moon_finished, Qt.ConnectionType.QueuedConnection)
        self._moon_worker.error.connect(        self._on_sync_error,    Qt.ConnectionType.QueuedConnection)
        self._moon_worker.no_permission.connect(self._on_moon_no_perm,  Qt.ConnectionType.QueuedConnection)
        self._moon_worker.start()

    def _on_moon_finished(self, observers: list):
        self._moon_sync_btn.setEnabled(True)
        self._set_status(f"Moon mining data updated – {len(observers)} observer(s).")
        self._refresh_moon_observer_combo()
        self._refresh_moon_tab()

    def _on_moon_no_perm(self):
        self._moon_sync_btn.setEnabled(True)
        self._set_status(
            "⚠  No moon-mining access.  The character must have "
            "Director or Accountant role in the corporation."
        )

    # ------------------------------------------------------------------
    # Tab refresh logic
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index: int):
        self._refresh_current_tab()

    def _refresh_current_tab(self):
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._refresh_mining_tab()
        elif idx == 1:
            self._refresh_moon_tab()
        elif idx == 2:
            self._refresh_summary_tab()

    def _get_date_range(self, combo: QComboBox) -> tuple[str | None, str | None]:
        idx  = combo.currentIndex()
        days = _PERIOD_OPTIONS[idx][1] if idx >= 0 else 30
        return _period_dates(days)

    def _get_selected_char_ids(self) -> list[int] | None:
        cid = self._selected_char_id()
        return [cid] if cid is not None else None

    # ── Mining tab ─────────────────────────────────────────────────────

    def _refresh_mining_tab(self):
        char_ids             = self._get_selected_char_ids()
        start_date, end_date = self._get_date_range(self._mining_period)
        rows = self._db.get_mining_history(char_ids, start_date, end_date)

        if not self._market_prices:
            try:
                self._market_prices = esi.get_market_prices()
            except Exception:
                pass

        self._mining_table.setSortingEnabled(False)
        self._mining_table.setRowCount(len(rows))

        total_units = 0
        total_m3    = 0.0
        total_isk   = 0.0
        dates_seen: set = set()
        types_seen: set = set()

        for r, row in enumerate(rows):
            qty    = row["quantity"] or 0
            vol    = (row["unit_volume"] or 0.0) * qty
            price  = self._market_prices.get(row["type_id"], 0.0)
            isk    = price * qty
            dname  = row["char_display_name"] or row["character_name"] or f"Char {row['character_id']}"
            tname  = row["resolved_type_name"] or row["type_name"] or f"Type {row['type_id']}"
            group  = row["group_name"] or ""

            total_units += qty
            total_m3    += vol
            total_isk   += isk
            dates_seen.add(row["mine_date"])
            types_seen.add(row["type_id"])

            # Colour-code ice types (group IDs 465 = Ice)
            tcolor = ICE_CYAN if group.lower() == "ice" else None

            self._mining_table.setItem(r, 0, _cell(dname))
            self._mining_table.setItem(r, 1, _cell(str(row["mine_date"])))
            self._mining_table.setItem(r, 2, _cell(row["solar_system_name"] or ""))
            self._mining_table.setItem(r, 3, _cell(tname, color=tcolor))
            self._mining_table.setItem(r, 4, _cell(group))
            self._mining_table.setItem(r, 5, _num_cell(qty, _fmt_quantity(qty)))
            self._mining_table.setItem(r, 6, _num_cell(vol, _fmt_m3(vol)))
            self._mining_table.setItem(r, 7, _num_cell(isk, _fmt_isk(isk)))
            self._mining_table.setItem(r, 8, _cell(str(row["id"])))

        self._mining_table.setSortingEnabled(True)

        # Update pills
        self._mp_rows.setText(f"Rows: {len(rows):,}")
        self._mp_total.setText(f"Total units: {_fmt_quantity(total_units)}")
        self._mp_m3.setText(   f"Volume: {_fmt_m3(total_m3)}")
        self._mp_isk.setText(  f"Est. ISK: {_fmt_isk(total_isk)}")
        self._mp_days.setText( f"Mining days: {len(dates_seen)}")
        self._mp_types.setText(f"Ore types: {len(types_seen)}")

    # ── Moon tab ───────────────────────────────────────────────────────

    def _refresh_moon_observer_combo(self):
        self._moon_observer.blockSignals(True)
        self._moon_observer.clear()
        self._moon_observer.addItem("All Observers", None)
        for obs_id, obs_name in self._db.get_observers():
            self._moon_observer.addItem(obs_name, obs_id)
        self._moon_observer.blockSignals(False)

    def _refresh_moon_tab(self):
        # Observer filter
        obs_idx = self._moon_observer.currentIndex()
        obs_ids = None
        if obs_idx > 0:
            obs_id = self._moon_observer.itemData(obs_idx)
            if obs_id is not None:
                obs_ids = [obs_id]

        rows = self._db.get_moon_mining(obs_ids)

        if not self._market_prices:
            try:
                self._market_prices = esi.get_market_prices()
            except Exception:
                pass

        # Apply character filter from moon char combo
        char_filter = self._moon_char_combo.currentData()

        # Refresh char combo
        chars_in_rows = {(r["character_id"], r["character_name"]) for r in rows}
        self._moon_char_combo.blockSignals(True)
        self._moon_char_combo.clear()
        self._moon_char_combo.addItem("Any character", None)
        for cid, cname in sorted(chars_in_rows, key=lambda x: x[1]):
            self._moon_char_combo.addItem(cname, cid)
        self._moon_char_combo.blockSignals(False)

        if char_filter is not None:
            rows = [r for r in rows if r["character_id"] == char_filter]

        self._moon_table.setSortingEnabled(False)
        self._moon_table.setRowCount(len(rows))

        total_units = 0
        total_m3    = 0.0
        total_isk   = 0.0
        chars_seen: set = set()
        types_seen: set = set()

        for r, row in enumerate(rows):
            qty   = row["quantity"] or 0
            vol   = (row["unit_volume"] or 0.0) * qty
            price = self._market_prices.get(row["type_id"], 0.0)
            isk   = price * qty
            group = row["group_name"] or ""

            total_units += qty
            total_m3    += vol
            total_isk   += isk
            chars_seen.add(row["character_id"])
            types_seen.add(row["type_id"])

            self._moon_table.setItem(r, 0, _cell(row["observer_name"] or ""))
            self._moon_table.setItem(r, 1, _cell(row["character_name"] or ""))
            self._moon_table.setItem(r, 2, _cell(row["type_name"] or ""))
            self._moon_table.setItem(r, 3, _cell(group))
            self._moon_table.setItem(r, 4, _num_cell(qty, _fmt_quantity(qty)))
            self._moon_table.setItem(r, 5, _num_cell(vol, _fmt_m3(vol)))
            self._moon_table.setItem(r, 6, _cell(str(row["last_updated"] or "")))

        self._moon_table.setSortingEnabled(True)

        self._moonp_chars.setText( f"Characters: {len(chars_seen)}")
        self._moonp_total.setText( f"Total units: {_fmt_quantity(total_units)}")
        self._moonp_m3.setText(    f"Volume: {_fmt_m3(total_m3)}")
        self._moonp_isk.setText(   f"Est. ISK: {_fmt_isk(total_isk)}")
        self._moonp_types.setText( f"Ore types: {len(types_seen)}")

    # ── Summary tab ────────────────────────────────────────────────────

    def _refresh_summary_tab(self):
        start_date, end_date = self._get_date_range(self._summary_period)

        if not self._market_prices:
            try:
                self._market_prices = esi.get_market_prices()
            except Exception:
                pass

        # By character
        char_rows = self._db.get_mining_summary_by_character(start_date, end_date)
        self._sum_char_table.setSortingEnabled(False)
        self._sum_char_table.setRowCount(len(char_rows))
        for r, row in enumerate(char_rows):
            self._sum_char_table.setItem(r, 0, _cell(row["character_name"] or ""))
            self._sum_char_table.setItem(r, 1, _cell(row["corporation_name"] or ""))
            qty = row["total_quantity"] or 0
            self._sum_char_table.setItem(r, 2, _num_cell(qty, _fmt_quantity(qty)))
            self._sum_char_table.setItem(r, 3, _num_cell(row["active_days"] or 0,
                                                          str(row["active_days"] or 0)))
            self._sum_char_table.setItem(r, 4, _num_cell(row["ore_types"] or 0,
                                                          str(row["ore_types"] or 0)))
        self._sum_char_table.setSortingEnabled(True)

        # By type
        type_rows = self._db.get_mining_summary_by_type(
            self._get_selected_char_ids(), start_date, end_date
        )
        self._sum_type_table.setSortingEnabled(False)
        self._sum_type_table.setRowCount(len(type_rows))
        for r, row in enumerate(type_rows):
            qty   = row["total_quantity"] or 0
            vol   = (row["unit_volume"] or 0.0) * qty
            price = self._market_prices.get(row["type_id"], 0.0)
            isk   = price * qty
            group = row["group_name"] or ""
            tname = row["type_name"] or f"Type {row['type_id']}"
            tcolor = ICE_CYAN if group.lower() == "ice" else None
            self._sum_type_table.setItem(r, 0, _cell(tname, color=tcolor))
            self._sum_type_table.setItem(r, 1, _cell(group))
            self._sum_type_table.setItem(r, 2, _num_cell(qty, _fmt_quantity(qty)))
            self._sum_type_table.setItem(r, 3, _num_cell(vol, _fmt_m3(vol)))
            self._sum_type_table.setItem(r, 4, _num_cell(isk, _fmt_isk(isk)))
        self._sum_type_table.setSortingEnabled(True)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
