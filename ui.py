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

import csv
import sys
from datetime import datetime, timedelta

from PyQt6.QtCore    import Qt, QDate, QRect, QSize, QThread, pyqtSignal, QTimer
from PyQt6.QtGui     import QBrush, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
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
    ("Custom range",  -1),   # -1 = use date pickers
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


def _kpi_card(title: str) -> "tuple[QFrame, QLabel]":
    """Create a KPI summary card.  Returns (outer_frame, value_label)."""
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame {{ background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px; }}"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(2)
    t = QLabel(title.upper())
    t.setStyleSheet(
        f"color: {TEXT_SEC}; font-size: 10px; font-weight: bold;"
        f" letter-spacing: 1px; background: transparent; border: none;"
    )
    lay.addWidget(t)
    v = QLabel("\u2014")
    v.setStyleSheet(
        f"color: {ORE_GOLD}; font-size: 20px; font-weight: 700;"
        f" background: transparent; border: none;"
    )
    lay.addWidget(v)
    return frame, v


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


# ── Chart widgets ────────────────────────────────────────────────────────────────

class BarChartWidget(QWidget):
    """Vertical bar chart – daily ISK timeline."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[str, float]] = []
        self.setMinimumHeight(180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
        )

    def set_data(self, data: list[tuple[str, float]]):
        self._data = list(data)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 72, 12, 14, 36
        p.fillRect(0, 0, W, H, QColor(PANEL_BG))
        if not self._data:
            p.setPen(QColor(TEXT_SEC))
            f = p.font(); f.setPointSize(10); p.setFont(f)
            p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "No mining data yet")
            return
        chart_w = W - pad_l - pad_r
        chart_h = H - pad_t - pad_b
        if chart_w < 1 or chart_h < 1:
            return
        max_val = max(v for _, v in self._data) or 1.0
        n       = len(self._data)
        spacing = 2
        bar_w   = max(2, chart_w // n - spacing)
        sf = p.font(); sf.setPointSize(8); p.setFont(sf)
        for i in range(5):
            frac = i / 4
            y    = pad_t + chart_h - int(frac * chart_h)
            p.setPen(QPen(QColor(BORDER if i == 0 else "#1e242b"), 1))
            p.drawLine(pad_l, y, W - pad_r, y)
            p.setPen(QColor(TEXT_SEC))
            p.drawText(QRect(0, y - 8, pad_l - 4, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       _fmt_isk(frac * max_val))
        p.setPen(Qt.PenStyle.NoPen)
        bar_color = QColor(ACCENT_BLUE)
        for i, (_, val) in enumerate(self._data):
            bh = int((val / max_val) * chart_h)
            if bh < 1:
                continue
            bx = pad_l + int(i * chart_w / n) + spacing
            by = pad_t + chart_h - bh
            p.setBrush(QBrush(bar_color))
            p.drawRoundedRect(bx, by, bar_w, bh, 2.0, 2.0)
        p.setPen(QColor(TEXT_SEC))
        step = max(1, n // 8)
        for i, (date_str, _) in enumerate(self._data):
            if i % step == 0:
                bx = pad_l + int(i * chart_w / n) + spacing
                p.drawText(QRect(bx - 14, H - pad_b + 4, bar_w + 28, 18),
                           Qt.AlignmentFlag.AlignCenter, date_str[5:])
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawLine(pad_l, pad_t + chart_h, W - pad_r, pad_t + chart_h)


class HBarChartWidget(QWidget):
    """Horizontal bar chart – top miners or top ore types."""

    _PALETTE = [ACCENT_BLUE, ORE_GOLD, ACCENT_GREEN, ICE_CYAN,
                WARN_YELLOW, DANGER_RED, "#a371f7", "#f0883e"]

    def __init__(self, parent=None, bar_color: str | None = None):
        super().__init__(parent)
        self._data:     list[tuple[str, float]] = []
        self._fmt       = _fmt_isk
        self._bar_color = bar_color
        self.setMinimumHeight(120)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"background-color: {PANEL_BG}; border: 1px solid {BORDER}; border-radius: 8px;"
        )

    def set_data(self, data: list[tuple[str, float]], fmt=None):
        self._data = list(data)[:8]
        self._fmt  = fmt or _fmt_isk
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        p.fillRect(0, 0, W, H, QColor(PANEL_BG))
        if not self._data:
            p.setPen(QColor(TEXT_SEC))
            f = p.font(); f.setPointSize(10); p.setFont(f)
            p.drawText(QRect(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, "No data")
            return
        n        = len(self._data)
        max_val  = max(v for _, v in self._data) or 1.0
        pad      = 10
        label_w  = 130
        val_w    = 90
        bar_area = max(1, W - pad - label_w - val_w - pad)
        row_h    = max(16, (H - pad * 2) // n)
        sf = p.font(); sf.setPointSize(9); p.setFont(sf)
        for i, (label, val) in enumerate(self._data):
            y     = pad + i * row_h
            bh    = max(4, row_h - 6)
            bw    = int((val / max_val) * bar_area)
            bx    = pad + label_w + 4
            color = QColor(self._bar_color) if self._bar_color else QColor(self._PALETTE[i % len(self._PALETTE)])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            if bw > 0:
                p.drawRoundedRect(bx, y + 3, bw, bh, 3.0, 3.0)
            p.setPen(QColor(TEXT_PRIMARY))
            p.drawText(QRect(pad, y, label_w, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label[:20])
            p.setPen(QColor(TEXT_SEC))
            p.drawText(QRect(bx + bar_area + 4, y, val_w - 4, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self._fmt(val))


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
                        # Collect unique group IDs then batch-resolve group names
                        group_ids = list({info["group_id"] for info in type_infos.values() if info.get("group_id")})
                        group_names = esi.get_groups_batch(group_ids, access)
                        for tid, info in type_infos.items():
                            gid = info.get("group_id")
                            self._db.save_type_info(
                                tid,
                                info.get("name", names.get(tid, f"Type {tid}")),
                                info.get("volume", 0.0),
                                gid,
                                group_names.get(gid) if gid else None,
                            )
                    # Back-fill group names for any previously cached types missing them
                    missing = self._db.get_types_missing_group_name()
                    if missing:
                        missing_gids = list({gid for _, gid in missing})
                        gnames = esi.get_groups_batch(missing_gids, access)
                        for type_id, gid in missing:
                            if gnames.get(gid):
                                self._db.update_group_name(type_id, gnames[gid])

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

            # Batch-fetch unknown type volumes + group names
            if all_type_ids_needed:
                self.progress.emit(f"Fetching {len(all_type_ids_needed)} ore type(s)…")
                type_infos = esi.get_types_batch(list(all_type_ids_needed), access)
                group_ids  = list({info["group_id"] for info in type_infos.values() if info.get("group_id")})
                group_names = esi.get_groups_batch(group_ids, access)
                for tid, info in type_infos.items():
                    gid = info.get("group_id")
                    self._db.save_type_info(tid, info.get("name", ""), info.get("volume", 0.0),
                                            gid, group_names.get(gid) if gid else None)
            # Back-fill group names for any previously cached types missing them
            missing = self._db.get_types_missing_group_name()
            if missing:
                missing_gids = list({gid for _, gid in missing})
                gnames = esi.get_groups_batch(missing_gids, access)
                for type_id, gid in missing:
                    if gnames.get(gid):
                        self._db.update_group_name(type_id, gnames[gid])

            self.finished.emit(result)

        except Exception as exc:
            self.error.emit(str(exc))


class PricesWorker(QThread):
    """Fetches market prices in the background and emits the result."""
    finished = pyqtSignal(dict)

    def run(self):
        try:
            self.finished.emit(esi.get_market_prices())
        except Exception:
            self.finished.emit({})


class GroupBackfillWorker(QThread):
    """Fetches group names for any type_cache rows missing them (public ESI, no auth needed)."""
    finished = pyqtSignal()

    def __init__(self, db: Database):
        super().__init__()
        self._db = db

    def run(self):
        try:
            missing = self._db.get_types_missing_group_name()
            if not missing:
                return
            group_ids = list({gid for _, gid in missing})
            gnames = esi.get_groups_batch(group_ids)   # no auth needed
            for type_id, gid in missing:
                if gnames.get(gid):
                    self._db.update_group_name(type_id, gnames[gid])
        except Exception:
            pass
        finally:
            self.finished.emit()


# ── Main window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, client_id: str):
        super().__init__()
        self._client_id     = client_id
        self._db            = Database()
        self._tokens        = auth.load_all_tokens()   # {str(char_id): token_dict}
        self._sync_worker:   SyncWorker | None              = None
        self._moon_worker:   MoonWorker | None              = None
        self._add_worker:    AddCharacterWorker | None      = None
        self._prices_worker: PricesWorker | None            = None
        self._group_worker:  GroupBackfillWorker | None     = None
        self._market_prices: dict[int, float]               = {}

        self.setWindowTitle("EVE Rock – Mining Tracker")
        self.setMinimumSize(1280, 720)
        self.resize(1600, 860)
        self._build_ui()
        self._load_existing_characters()
        self._fetch_prices_bg()   # load prices in background on startup
        self._backfill_groups_bg()  # fill missing group names at startup

    def _fetch_prices_bg(self):
        if self._prices_worker and self._prices_worker.isRunning():
            return
        self._prices_worker = PricesWorker()
        self._prices_worker.finished.connect(self._on_prices_fetched, Qt.ConnectionType.QueuedConnection)
        self._prices_worker.start()

    def _backfill_groups_bg(self):
        if self._group_worker and self._group_worker.isRunning():
            return
        self._group_worker = GroupBackfillWorker(self._db)
        self._group_worker.finished.connect(self._refresh_current_tab, Qt.ConnectionType.QueuedConnection)
        self._group_worker.start()

    def _on_prices_fetched(self, prices: dict):
        if prices:
            self._market_prices = prices
            self._refresh_current_tab()

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
        self._char_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._char_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._char_list.customContextMenuRequested.connect(self._on_char_context_menu)
        self._char_list.itemSelectionChanged.connect(self._on_char_selected)
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
        self._tab_dash    = self._build_tab_dashboard()
        self._tab_mining  = self._build_tab_mining()
        self._tab_moon    = self._build_tab_moon()
        self._tab_summary = self._build_tab_summary()
        self._tabs.addTab(self._tab_dash,    "🏠  Dashboard")
        self._tabs.addTab(self._tab_mining,  "⛏  Character Mining")
        self._tabs.addTab(self._tab_moon,    "🌙  Moon Mining")
        self._tabs.addTab(self._tab_summary, "📊  Summary")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self._tabs)
        return panel

    # ── Tab: Dashboard ────────────────────────────────────────────────

    def _build_tab_dashboard(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(12)

        # Period filter
        fbar = QHBoxLayout(); fbar.setSpacing(12)
        fbar.addWidget(QLabel("Period:"))
        self._dash_period = QComboBox()
        for label, _ in _PERIOD_OPTIONS:
            self._dash_period.addItem(label)
        self._dash_period.setCurrentIndex(1)   # 30 days default
        self._dash_period.currentIndexChanged.connect(self._on_dash_period_changed)
        fbar.addWidget(self._dash_period)

        today = QDate.currentDate()
        self._dash_from_lbl = QLabel("From:")
        self._dash_from_lbl.setVisible(False)
        fbar.addWidget(self._dash_from_lbl)
        self._dash_from = QDateEdit(today.addDays(-30))
        self._dash_from.setCalendarPopup(True)
        self._dash_from.setDisplayFormat("yyyy-MM-dd")
        self._dash_from.setVisible(False)
        self._dash_from.dateChanged.connect(self._refresh_dashboard_tab)
        fbar.addWidget(self._dash_from)

        self._dash_to_lbl = QLabel("To:")
        self._dash_to_lbl.setVisible(False)
        fbar.addWidget(self._dash_to_lbl)
        self._dash_to = QDateEdit(today)
        self._dash_to.setCalendarPopup(True)
        self._dash_to.setDisplayFormat("yyyy-MM-dd")
        self._dash_to.setVisible(False)
        self._dash_to.dateChanged.connect(self._refresh_dashboard_tab)
        fbar.addWidget(self._dash_to)
        fbar.addStretch()
        lay.addLayout(fbar)

        # KPI cards
        kpi_row = QHBoxLayout(); kpi_row.setSpacing(12)
        isk_card,   self._kpi_isk_lbl   = _kpi_card("Est. ISK")
        vol_card,   self._kpi_vol_lbl   = _kpi_card("Volume")
        chars_card, self._kpi_chars_lbl = _kpi_card("Characters")
        days_card,  self._kpi_days_lbl  = _kpi_card("Mining Days")
        types_card, self._kpi_types_lbl = _kpi_card("Ore Types")
        for card in (isk_card, vol_card, chars_card, days_card, types_card):
            kpi_row.addWidget(card)
        lay.addLayout(kpi_row)

        # Charts row
        charts = QHBoxLayout(); charts.setSpacing(12)

        tl_col = QVBoxLayout(); tl_col.setSpacing(6)
        tl_lbl = QLabel("ISK PER DAY")
        tl_lbl.setObjectName("section_label")
        tl_col.addWidget(tl_lbl)
        self._timeline_chart = BarChartWidget()
        tl_col.addWidget(self._timeline_chart, 1)
        charts.addLayout(tl_col, 3)

        rt_col = QVBoxLayout(); rt_col.setSpacing(6)
        tc_lbl = QLabel("TOP CHARACTERS  (Est. ISK)")
        tc_lbl.setObjectName("section_label")
        rt_col.addWidget(tc_lbl)
        self._top_chars_chart = HBarChartWidget(bar_color=ACCENT_BLUE)
        self._top_chars_chart.setMinimumHeight(140)
        rt_col.addWidget(self._top_chars_chart, 1)
        tt_lbl = QLabel("TOP ORE TYPES  (Est. ISK)")
        tt_lbl.setObjectName("section_label")
        rt_col.addWidget(tt_lbl)
        self._top_types_chart = HBarChartWidget(bar_color=ORE_GOLD)
        self._top_types_chart.setMinimumHeight(140)
        rt_col.addWidget(self._top_types_chart, 1)
        charts.addLayout(rt_col, 2)

        lay.addLayout(charts, 1)
        return w

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
        self._mining_period.currentIndexChanged.connect(self._on_mining_period_changed)
        fbar.addWidget(self._mining_period)

        today = QDate.currentDate()
        self._mining_from_lbl = QLabel("From:")
        self._mining_from_lbl.setVisible(False)
        fbar.addWidget(self._mining_from_lbl)
        self._mining_from = QDateEdit(today.addDays(-30))
        self._mining_from.setCalendarPopup(True)
        self._mining_from.setDisplayFormat("yyyy-MM-dd")
        self._mining_from.setVisible(False)
        self._mining_from.dateChanged.connect(self._refresh_mining_tab)
        fbar.addWidget(self._mining_from)

        self._mining_to_lbl = QLabel("To:")
        self._mining_to_lbl.setVisible(False)
        fbar.addWidget(self._mining_to_lbl)
        self._mining_to = QDateEdit(today)
        self._mining_to.setCalendarPopup(True)
        self._mining_to.setDisplayFormat("yyyy-MM-dd")
        self._mining_to.setVisible(False)
        self._mining_to.dateChanged.connect(self._refresh_mining_tab)
        fbar.addWidget(self._mining_to)

        fbar.addStretch()

        exp_btn = QPushButton("⬇  Export CSV")
        exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_btn.setToolTip("Export current view to CSV")
        exp_btn.clicked.connect(lambda: self._export_table_to_csv(self._mining_table, "character_mining"))
        fbar.addWidget(exp_btn)

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
        root = QHBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left character-filter panel ───────────────────────────────
        char_panel = QWidget()
        char_panel.setFixedWidth(140)
        char_panel.setStyleSheet(
            f"background-color: {PANEL_BG}; border-right: 1px solid {BORDER};"
        )
        cp_lay = QVBoxLayout(char_panel)
        cp_lay.setContentsMargins(8, 10, 8, 10)
        cp_lay.setSpacing(6)

        ch_hdr = QLabel("CHARACTERS")
        ch_hdr.setObjectName("section_label")
        cp_lay.addWidget(ch_hdr)

        self._moon_char_list = QListWidget()
        self._moon_char_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._moon_char_list.setToolTip("Ctrl+click / Shift+click for multiple.\nNo selection = all characters.")
        self._moon_char_list.setStyleSheet("background: transparent; border: none;")
        self._moon_char_list.itemSelectionChanged.connect(self._refresh_moon_tab)
        cp_lay.addWidget(self._moon_char_list)

        clear_btn = QPushButton("Show All")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setToolTip("Clear selection to show all characters")
        clear_btn.clicked.connect(self._moon_char_list.clearSelection)
        cp_lay.addWidget(clear_btn)

        root.addWidget(char_panel)

        # ── Right content area ────────────────────────────────────────
        right = QWidget()
        lay   = QVBoxLayout(right)
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
        fbar.addWidget(QLabel("Period:"))
        self._moon_period = QComboBox()
        for label, _ in _PERIOD_OPTIONS:
            self._moon_period.addItem(label)
        self._moon_period.setCurrentIndex(4)  # "All time" default
        self._moon_period.currentIndexChanged.connect(self._on_moon_period_changed)
        fbar.addWidget(self._moon_period)

        today = QDate.currentDate()
        self._moon_from_lbl = QLabel("From:")
        self._moon_from_lbl.setVisible(False)
        fbar.addWidget(self._moon_from_lbl)
        self._moon_from = QDateEdit(today.addDays(-30))
        self._moon_from.setCalendarPopup(True)
        self._moon_from.setDisplayFormat("yyyy-MM-dd")
        self._moon_from.setVisible(False)
        self._moon_from.dateChanged.connect(self._refresh_moon_tab)
        fbar.addWidget(self._moon_from)

        self._moon_to_lbl = QLabel("To:")
        self._moon_to_lbl.setVisible(False)
        fbar.addWidget(self._moon_to_lbl)
        self._moon_to = QDateEdit(today)
        self._moon_to.setCalendarPopup(True)
        self._moon_to.setDisplayFormat("yyyy-MM-dd")
        self._moon_to.setVisible(False)
        self._moon_to.dateChanged.connect(self._refresh_moon_tab)
        fbar.addWidget(self._moon_to)

        fbar.addSpacing(16)
        fbar.addWidget(QLabel("Observer:"))
        self._moon_observer = QComboBox()
        self._moon_observer.addItem("All Observers", None)
        self._moon_observer.currentIndexChanged.connect(self._refresh_moon_tab)
        fbar.addWidget(self._moon_observer)

        fbar.addSpacing(16)
        fbar.addWidget(QLabel("Tax %:"))
        self._moon_tax = QDoubleSpinBox()
        self._moon_tax.setRange(0.0, 100.0)
        self._moon_tax.setValue(15.0)
        self._moon_tax.setSuffix(" %")
        self._moon_tax.setDecimals(1)
        self._moon_tax.setFixedWidth(90)
        self._moon_tax.setToolTip("Corp tax rate applied to Est. ISK")
        self._moon_tax.valueChanged.connect(self._refresh_moon_tab)
        fbar.addWidget(self._moon_tax)

        fbar.addStretch()

        exp_btn = QPushButton("⬇  Export CSV")
        exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_btn.setToolTip("Export current view to CSV")
        exp_btn.clicked.connect(lambda: self._export_table_to_csv(self._moon_table, "moon_mining"))
        fbar.addWidget(exp_btn)

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
        self._moonp_tax    = _pill("Tax (15%): —")
        self._moonp_types  = _pill("Ore types: —")
        for p in (self._moonp_chars, self._moonp_total, self._moonp_m3,
                  self._moonp_isk, self._moonp_tax, self._moonp_types):
            prow.addWidget(p)
        prow.addStretch()
        lay.addLayout(prow)

        # Table
        self._moon_table = QTableWidget()
        self._moon_table.setColumnCount(9)
        self._moon_table.setHorizontalHeaderLabels([
            "Observer / Refinery", "Character", "Ore / Ice Type",
            "Group", "Quantity", "Est. m³", "Est. ISK", "Tax", "Last Updated"
        ])
        _setup_table(self._moon_table)
        hv = self._moon_table.horizontalHeader()
        hv.setMinimumSectionSize(70)
        for col, mode in [
            (0, QHeaderView.ResizeMode.Interactive),   # Observer / Refinery
            (1, QHeaderView.ResizeMode.Interactive),   # Character
            (2, QHeaderView.ResizeMode.Stretch),       # Ore / Ice Type
            (3, QHeaderView.ResizeMode.Interactive),   # Group
            (4, QHeaderView.ResizeMode.ResizeToContents),
            (5, QHeaderView.ResizeMode.ResizeToContents),
            (6, QHeaderView.ResizeMode.ResizeToContents),
            (7, QHeaderView.ResizeMode.ResizeToContents),
            (8, QHeaderView.ResizeMode.ResizeToContents),
        ]:
            hv.setSectionResizeMode(col, mode)
        self._moon_table.setColumnWidth(0, 220)
        self._moon_table.setColumnWidth(1, 140)
        self._moon_table.setColumnWidth(3, 110)
        lay.addWidget(self._moon_table)

        root.addWidget(right, 1)
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
        self._summary_period.currentIndexChanged.connect(self._on_summary_period_changed)
        fbar.addWidget(self._summary_period)

        today = QDate.currentDate()
        self._summary_from_lbl = QLabel("From:")
        self._summary_from_lbl.setVisible(False)
        fbar.addWidget(self._summary_from_lbl)
        self._summary_from = QDateEdit(today.addDays(-30))
        self._summary_from.setCalendarPopup(True)
        self._summary_from.setDisplayFormat("yyyy-MM-dd")
        self._summary_from.setVisible(False)
        self._summary_from.dateChanged.connect(self._refresh_summary_tab)
        fbar.addWidget(self._summary_from)

        self._summary_to_lbl = QLabel("To:")
        self._summary_to_lbl.setVisible(False)
        fbar.addWidget(self._summary_to_lbl)
        self._summary_to = QDateEdit(today)
        self._summary_to.setCalendarPopup(True)
        self._summary_to.setDisplayFormat("yyyy-MM-dd")
        self._summary_to.setVisible(False)
        self._summary_to.dateChanged.connect(self._refresh_summary_tab)
        fbar.addWidget(self._summary_to)

        fbar.addStretch()

        exp_btn = QPushButton("⬇  Export CSV")
        exp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exp_btn.setToolTip("Export both summary tables to CSV")
        exp_btn.clicked.connect(self._export_summary_csv)
        fbar.addWidget(exp_btn)

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
        """Returns single char id for operations that need exactly one char (e.g. moon sync)."""
        item = self._char_list.currentItem()
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)  # None = "All"

    def _get_selected_char_ids(self) -> list[int] | None:
        """Returns list of selected char IDs, or None meaning 'all characters'."""
        selected = self._char_list.selectedItems()
        if not selected:
            return None
        ids = [item.data(Qt.ItemDataRole.UserRole) for item in selected]
        if None in ids:   # "All Characters" item is among selections
            return None
        return ids if ids else None

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

    # ── Export helpers ──────────────────────────────────────────────

    def _export_table_to_csv(self, table: QTableWidget, default_stem: str) -> None:
        """Write every visible (non-hidden) column of *table* to a user-chosen CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV",
            f"{default_stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return
        cols = table.columnCount()
        rows = table.rowCount()
        headers = [table.horizontalHeaderItem(c).text() for c in range(cols)]
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for r in range(rows):
                    row_data = []
                    for c in range(cols):
                        item = table.item(r, c)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            self._set_status(f"Exported {rows} rows → {path}")
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))

    def _export_summary_csv(self) -> None:
        """Export both summary tables to separate CSV files (adds _by_character / _by_type suffixes)."""
        stem = f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Summary CSV (base name)",
            f"{stem}.csv",
            "CSV files (*.csv)"
        )
        if not path:
            return
        base = path[:-4] if path.lower().endswith(".csv") else path
        for table, suffix in [
            (self._sum_char_table, "_by_character"),
            (self._sum_type_table, "_by_type"),
        ]:
            out = base + suffix + ".csv"
            cols = table.columnCount()
            rows = table.rowCount()
            headers = [table.horizontalHeaderItem(c).text() for c in range(cols)]
            try:
                with open(out, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for r in range(rows):
                        writer.writerow([
                            (table.item(r, c).text() if table.item(r, c) else "")
                            for c in range(cols)
                        ])
            except OSError as e:
                QMessageBox.warning(self, "Export failed", str(e))
                return
        self._set_status(f"Exported summary → {base}_by_character.csv / _by_type.csv")

    # ── Sync workers ────────────────────────────────────────────────

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
        self._fetch_prices_bg()   # refresh prices in background after sync
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
        if not hasattr(self, '_tabs'):
            return
        idx = self._tabs.currentIndex()
        if idx == 0:
            self._refresh_dashboard_tab()
        elif idx == 1:
            self._refresh_mining_tab()
        elif idx == 2:
            self._refresh_moon_tab()
        elif idx == 3:
            self._refresh_summary_tab()

    def _on_dash_period_changed(self):
        idx    = self._dash_period.currentIndex()
        days   = _PERIOD_OPTIONS[idx][1] if idx >= 0 else 30
        custom = (days == -1)
        self._dash_from_lbl.setVisible(custom)
        self._dash_from.setVisible(custom)
        self._dash_to_lbl.setVisible(custom)
        self._dash_to.setVisible(custom)
        self._refresh_dashboard_tab()

    def _on_mining_period_changed(self):
        idx  = self._mining_period.currentIndex()
        days = _PERIOD_OPTIONS[idx][1] if idx >= 0 else 30
        custom = (days == -1)
        self._mining_from_lbl.setVisible(custom)
        self._mining_from.setVisible(custom)
        self._mining_to_lbl.setVisible(custom)
        self._mining_to.setVisible(custom)
        self._refresh_mining_tab()

    def _on_moon_period_changed(self):
        idx  = self._moon_period.currentIndex()
        days = _PERIOD_OPTIONS[idx][1] if idx >= 0 else None
        custom = (days == -1)
        self._moon_from_lbl.setVisible(custom)
        self._moon_from.setVisible(custom)
        self._moon_to_lbl.setVisible(custom)
        self._moon_to.setVisible(custom)
        self._refresh_moon_tab()

    def _on_summary_period_changed(self):
        idx  = self._summary_period.currentIndex()
        days = _PERIOD_OPTIONS[idx][1] if idx >= 0 else 30
        custom = (days == -1)
        self._summary_from_lbl.setVisible(custom)
        self._summary_from.setVisible(custom)
        self._summary_to_lbl.setVisible(custom)
        self._summary_to.setVisible(custom)
        self._refresh_summary_tab()

    def _get_date_range(self, combo: QComboBox,
                        from_edit: QDateEdit | None = None,
                        to_edit:   QDateEdit | None = None) -> tuple[str | None, str | None]:
        idx  = combo.currentIndex()
        days = _PERIOD_OPTIONS[idx][1] if idx >= 0 else 30
        if days == -1 and from_edit and to_edit:
            return (from_edit.date().toString("yyyy-MM-dd"),
                    to_edit.date().toString("yyyy-MM-dd"))
        return _period_dates(days)

    def _get_selected_char_ids(self) -> list[int] | None:
        cid = self._selected_char_id()
        return [cid] if cid is not None else None

    # ── Dashboard tab ──────────────────────────────────────────────────

    def _refresh_dashboard_tab(self):
        char_ids             = self._get_selected_char_ids()
        start_date, end_date = self._get_date_range(
            self._dash_period, self._dash_from, self._dash_to
        )
        # Per-day totals for timeline
        daily_rows = self._db.get_daily_mining_totals(char_ids, start_date, end_date)
        day_isk: dict[str, float] = {}
        total_units = 0
        total_m3    = 0.0
        for row in daily_rows:
            qty   = row["total_quantity"] or 0
            price = self._market_prices.get(row["type_id"], 0.0)
            isk   = price * qty
            day_isk[row["mine_date"]] = day_isk.get(row["mine_date"], 0.0) + isk
            total_units += qty
            total_m3    += (row["unit_volume"] or 0.0) * qty
        self._timeline_chart.set_data(sorted(day_isk.items()))
        total_isk = sum(day_isk.values())

        # Top characters by ISK
        char_type_rows = self._db.get_mining_isk_by_character(char_ids, start_date, end_date)
        char_isk: dict[str, float] = {}
        for row in char_type_rows:
            price = self._market_prices.get(row["type_id"], 0.0)
            isk   = price * (row["total_quantity"] or 0)
            char_isk[row["character_name"]] = char_isk.get(row["character_name"], 0.0) + isk
        top_chars = sorted(char_isk.items(), key=lambda x: x[1], reverse=True)[:8]
        self._top_chars_chart.set_data(top_chars, _fmt_isk)

        # Top ore types by ISK
        type_rows = self._db.get_mining_summary_by_type(char_ids, start_date, end_date)
        ore_isk: list[tuple[str, float]] = []
        for row in type_rows:
            price = self._market_prices.get(row["type_id"], 0.0)
            isk   = price * (row["total_quantity"] or 0)
            ore_isk.append((row["type_name"] or f"Type {row['type_id']}", isk))
        ore_isk.sort(key=lambda x: x[1], reverse=True)
        self._top_types_chart.set_data(ore_isk[:8], _fmt_isk)

        # KPI cards
        self._kpi_isk_lbl.setText(_fmt_isk(total_isk))
        self._kpi_vol_lbl.setText(_fmt_m3(total_m3))
        self._kpi_chars_lbl.setText(str(len(char_isk)))
        self._kpi_days_lbl.setText(str(len(day_isk)))
        self._kpi_types_lbl.setText(str(len(type_rows)))

    # ── Mining tab ─────────────────────────────────────────────────────

    def _refresh_mining_tab(self):
        char_ids             = self._get_selected_char_ids()
        start_date, end_date = self._get_date_range(self._mining_period, self._mining_from, self._mining_to)
        rows = self._db.get_mining_history(char_ids, start_date, end_date)

        self._mining_table.setSortingEnabled(False)
        self._mining_table.setUpdatesEnabled(False)
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

        self._mining_table.setUpdatesEnabled(True)
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

        start_date, end_date = self._get_date_range(self._moon_period, self._moon_from, self._moon_to)
        rows = self._db.get_moon_mining(obs_ids, start_date, end_date)

        # Refresh character list widget, preserving selection by name
        chars_in_rows = {(r["character_id"], r["character_name"]) for r in rows}
        prev_selected = {item.data(Qt.ItemDataRole.UserRole)
                         for item in self._moon_char_list.selectedItems()}
        self._moon_char_list.blockSignals(True)
        self._moon_char_list.clear()
        for cid, cname in sorted(chars_in_rows, key=lambda x: x[1]):
            item = QListWidgetItem(cname)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            item.setSizeHint(QSize(0, 22))  # compact row height
            self._moon_char_list.addItem(item)
            if cid in prev_selected:
                item.setSelected(True)
        self._moon_char_list.blockSignals(False)

        # Apply character filter — empty selection means all
        selected_ids = {item.data(Qt.ItemDataRole.UserRole)
                        for item in self._moon_char_list.selectedItems()}
        if selected_ids:
            rows = [r for r in rows if r["character_id"] in selected_ids]

        tax_rate = self._moon_tax.value() / 100.0

        self._moon_table.setSortingEnabled(False)
        self._moon_table.setUpdatesEnabled(False)
        # +1 row for totals footer
        self._moon_table.setRowCount(len(rows) + 1)

        total_units = 0
        total_m3    = 0.0
        total_isk   = 0.0
        total_tax   = 0.0
        chars_seen: set = set()
        types_seen: set = set()

        for r, row in enumerate(rows):
            qty   = row["quantity"] or 0
            vol   = (row["unit_volume"] or 0.0) * qty
            price = self._market_prices.get(row["type_id"], 0.0)
            isk   = price * qty
            tax   = isk * tax_rate
            group = row["group_name"] or ""

            total_units += qty
            total_m3    += vol
            total_isk   += isk
            total_tax   += tax
            chars_seen.add(row["character_id"])
            types_seen.add(row["type_id"])

            self._moon_table.setItem(r, 0, _cell(row["observer_name"] or ""))
            self._moon_table.setItem(r, 1, _cell(row["character_name"] or ""))
            self._moon_table.setItem(r, 2, _cell(row["type_name"] or ""))
            self._moon_table.setItem(r, 3, _cell(group))
            self._moon_table.setItem(r, 4, _num_cell(qty, _fmt_quantity(qty)))
            self._moon_table.setItem(r, 5, _num_cell(vol, _fmt_m3(vol)))
            self._moon_table.setItem(r, 6, _num_cell(isk, _fmt_isk(isk)))
            self._moon_table.setItem(r, 7, _num_cell(tax, _fmt_isk(tax)))
            self._moon_table.setItem(r, 8, _cell(str(row["last_updated"] or "")))

        # Totals row
        tr = len(rows)
        bold = QFont(); bold.setBold(True)
        def _total_cell(text: str, val: float = 0) -> QTableWidgetItem:
            item = _num_cell(val, text)
            item.setFont(bold)
            item.setForeground(QColor(ORE_GOLD))
            return item
        def _total_label(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(text)
            item.setFont(bold)
            item.setForeground(QColor(ORE_GOLD))
            return item
        self._moon_table.setItem(tr, 0, _total_label("TOTALS"))
        self._moon_table.setItem(tr, 1, _total_label(""))
        self._moon_table.setItem(tr, 2, _total_label(""))
        self._moon_table.setItem(tr, 3, _total_label(""))
        self._moon_table.setItem(tr, 4, _total_cell(_fmt_quantity(total_units), total_units))
        self._moon_table.setItem(tr, 5, _total_cell(_fmt_m3(total_m3), total_m3))
        self._moon_table.setItem(tr, 6, _total_cell(_fmt_isk(total_isk), total_isk))
        self._moon_table.setItem(tr, 7, _total_cell(_fmt_isk(total_tax), total_tax))
        self._moon_table.setItem(tr, 8, _total_label(""))

        self._moon_table.setUpdatesEnabled(True)
        self._moon_table.setSortingEnabled(True)

        pct = self._moon_tax.value()
        self._moonp_chars.setText( f"Characters: {len(chars_seen)}")
        self._moonp_total.setText( f"Total units: {_fmt_quantity(total_units)}")
        self._moonp_m3.setText(    f"Volume: {_fmt_m3(total_m3)}")
        self._moonp_isk.setText(   f"Est. ISK: {_fmt_isk(total_isk)}")
        self._moonp_tax.setText(   f"Tax ({pct:.0f}%): {_fmt_isk(total_tax)}")
        self._moonp_types.setText( f"Ore types: {len(types_seen)}")

    # ── Summary tab ────────────────────────────────────────────────────

    def _refresh_summary_tab(self):
        start_date, end_date = self._get_date_range(self._summary_period, self._summary_from, self._summary_to)

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
