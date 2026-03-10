"""
EVE Rock – SQLite history store.

Data is persisted in ~/.eve_rock_data.db so history accumulates beyond ESI's
30-day rolling window.

Tables
------
characters          – known characters (id, name, corp)
type_cache          – ore/ice/gas type metadata (name, volume, group)
mining_ledger       – character mining entries  (upserted per date/system/type)
moon_mining         – current lunar-cycle mining per observer/character/type
moon_mining_history – archived completed moon cycles
"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".eve_rock_data.db"


class Database:
    """Thread-safe SQLite wrapper using WAL journal mode."""

    def __init__(self, path: Path = DB_PATH):
        self._path  = path
        self._lock  = threading.Lock()
        self._local = threading.local()
        # Ensure schema on first use
        self._get_conn()
        self._create_schema()

    # ------------------------------------------------------------------
    # Connection management (one connection per OS thread)
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(str(self._path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    @property
    def conn(self) -> sqlite3.Connection:
        return self._get_conn()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_schema(self) -> None:
        with self._lock:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS characters (
                    character_id     INTEGER PRIMARY KEY,
                    character_name   TEXT NOT NULL,
                    corporation_id   INTEGER,
                    corporation_name TEXT,
                    last_synced      TEXT
                );

                CREATE TABLE IF NOT EXISTS type_cache (
                    type_id      INTEGER PRIMARY KEY,
                    type_name    TEXT,
                    volume       REAL,
                    group_id     INTEGER,
                    group_name   TEXT,
                    cached_at    TEXT
                );

                CREATE TABLE IF NOT EXISTS mining_ledger (
                    id                INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id      INTEGER NOT NULL,
                    mine_date         TEXT    NOT NULL,
                    solar_system_id   INTEGER,
                    solar_system_name TEXT,
                    type_id           INTEGER,
                    type_name         TEXT,
                    quantity          INTEGER,
                    first_recorded    TEXT,
                    last_updated      TEXT,
                    UNIQUE(character_id, mine_date, solar_system_id, type_id)
                );
                CREATE INDEX IF NOT EXISTS idx_ml_char ON mining_ledger(character_id);
                CREATE INDEX IF NOT EXISTS idx_ml_date ON mining_ledger(mine_date);
                CREATE INDEX IF NOT EXISTS idx_ml_type ON mining_ledger(type_id);

                CREATE TABLE IF NOT EXISTS moon_mining (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    observer_id      INTEGER NOT NULL,
                    observer_name    TEXT,
                    character_id     INTEGER,
                    character_name   TEXT,
                    recorded_corp_id INTEGER,
                    type_id          INTEGER,
                    type_name        TEXT,
                    quantity         INTEGER,
                    last_updated     TEXT,
                    first_recorded   TEXT,
                    UNIQUE(observer_id, character_id, type_id)
                );
                CREATE INDEX IF NOT EXISTS idx_mm_obs  ON moon_mining(observer_id);
                CREATE INDEX IF NOT EXISTS idx_mm_char ON moon_mining(character_id);

                CREATE TABLE IF NOT EXISTS moon_mining_history (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    observer_id    INTEGER NOT NULL,
                    observer_name  TEXT,
                    character_id   INTEGER,
                    character_name TEXT,
                    type_id        INTEGER,
                    type_name      TEXT,
                    quantity       INTEGER,
                    cycle_end_date TEXT,
                    archived_at    TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mmh_obs ON moon_mining_history(observer_id);
            """)
            self.conn.commit()

    # ------------------------------------------------------------------
    # Characters
    # ------------------------------------------------------------------

    def save_character(self, char_id: int, name: str, corp_id: int | None,
                       corp_name: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock:
            self.conn.execute("""
                INSERT INTO characters
                    (character_id, character_name, corporation_id, corporation_name, last_synced)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(character_id) DO UPDATE SET
                    character_name   = excluded.character_name,
                    corporation_id   = excluded.corporation_id,
                    corporation_name = excluded.corporation_name,
                    last_synced      = excluded.last_synced
            """, (char_id, name, corp_id, corp_name, now))
            self.conn.commit()

    def get_all_characters(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM characters ORDER BY character_name"
        ).fetchall()

    def get_character(self, char_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM characters WHERE character_id = ?", (char_id,)
        ).fetchone()

    # ------------------------------------------------------------------
    # Type cache
    # ------------------------------------------------------------------

    def save_type_info(self, type_id: int, name: str, volume: float,
                       group_id: int | None = None,
                       group_name: str | None = None) -> None:
        now = datetime.utcnow().isoformat()
        with self._lock:
            self.conn.execute("""
                INSERT INTO type_cache (type_id, type_name, volume, group_id, group_name, cached_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(type_id) DO UPDATE SET
                    type_name  = excluded.type_name,
                    volume     = excluded.volume,
                    group_id   = excluded.group_id,
                    group_name = excluded.group_name,
                    cached_at  = excluded.cached_at
            """, (type_id, name, volume, group_id, group_name, now))
            self.conn.commit()

    def get_type_info(self, type_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM type_cache WHERE type_id = ?", (type_id,)
        ).fetchone()

    def get_types_missing_group_name(self) -> list[tuple[int, int]]:
        """Return [(type_id, group_id)] for cached types that have a group_id but no group_name yet."""
        rows = self.conn.execute(
            "SELECT type_id, group_id FROM type_cache "
            "WHERE group_id IS NOT NULL AND (group_name IS NULL OR group_name = '')"
        ).fetchall()
        return [(r["type_id"], r["group_id"]) for r in rows]

    def update_group_name(self, type_id: int, group_name: str) -> None:
        """Update only the group_name for an existing type_cache entry."""
        with self._lock:
            self.conn.execute(
                "UPDATE type_cache SET group_name = ? WHERE type_id = ?",
                (group_name, type_id)
            )
            self.conn.commit()

    def get_known_type_ids(self) -> set[int]:
        rows = self.conn.execute("SELECT type_id FROM type_cache").fetchall()
        return {r[0] for r in rows}

    # ------------------------------------------------------------------
    # Mining ledger
    # ------------------------------------------------------------------

    def save_mining_entries(self, char_id: int, entries: list[dict]) -> None:
        """
        Upsert character mining entries.
        Each entry must contain: date, solar_system_id, solar_system_name,
        type_id, type_name, quantity.
        """
        now = datetime.utcnow().isoformat()
        with self._lock:
            for e in entries:
                self.conn.execute("""
                    INSERT INTO mining_ledger
                        (character_id, mine_date, solar_system_id, solar_system_name,
                         type_id, type_name, quantity, first_recorded, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(character_id, mine_date, solar_system_id, type_id) DO UPDATE SET
                        solar_system_name = excluded.solar_system_name,
                        type_name         = excluded.type_name,
                        quantity          = excluded.quantity,
                        last_updated      = excluded.last_updated
                """, (
                    char_id,
                    str(e.get("date", "")),
                    e.get("solar_system_id"),
                    e.get("solar_system_name", ""),
                    e.get("type_id"),
                    e.get("type_name", ""),
                    e.get("quantity", 0),
                    now, now,
                ))
            self.conn.commit()

    def get_mining_history(
        self,
        char_ids:   list[int] | None = None,
        start_date: str | None = None,
        end_date:   str | None = None,
    ) -> list[sqlite3.Row]:
        """
        Query mining history, optionally filtered by character(s) and date range.
        Returns rows sorted by date DESC.
        """
        filters: list[str] = []
        params:  list      = []

        if char_ids:
            ph = ",".join("?" * len(char_ids))
            filters.append(f"m.character_id IN ({ph})")
            params.extend(char_ids)
        if start_date:
            filters.append("m.mine_date >= ?");  params.append(start_date)
        if end_date:
            filters.append("m.mine_date <= ?");  params.append(end_date)

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT  m.*,
                    COALESCE(m.type_name,
                             c2.type_name,
                             'Type ' || m.type_id)  AS resolved_type_name,
                    COALESCE(c2.volume, 0.0)         AS unit_volume,
                    COALESCE(c2.group_name, '')       AS group_name,
                    c.character_name                  AS char_display_name
            FROM    mining_ledger m
            LEFT JOIN characters  c  ON m.character_id = c.character_id
            LEFT JOIN type_cache  c2 ON m.type_id      = c2.type_id
            {where}
            ORDER BY m.mine_date DESC, c.character_name, m.type_name
        """
        return self.conn.execute(sql, params).fetchall()

    def get_mining_summary_by_type(
        self,
        char_ids:   list[int] | None = None,
        start_date: str | None = None,
        end_date:   str | None = None,
    ) -> list[sqlite3.Row]:
        filters: list[str] = []
        params:  list      = []
        if char_ids:
            ph = ",".join("?" * len(char_ids))
            filters.append(f"m.character_id IN ({ph})")
            params.extend(char_ids)
        if start_date:
            filters.append("m.mine_date >= ?");  params.append(start_date)
        if end_date:
            filters.append("m.mine_date <= ?");  params.append(end_date)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT  m.type_id,
                    COALESCE(tc.type_name, m.type_name, 'Type '||m.type_id) AS type_name,
                    COALESCE(tc.group_name, '')                              AS group_name,
                    COALESCE(tc.volume, 0.0)                                as unit_volume,
                    SUM(m.quantity)                                          AS total_quantity
            FROM    mining_ledger m
            LEFT JOIN type_cache tc ON m.type_id = tc.type_id
            {where}
            GROUP BY m.type_id
            ORDER BY total_quantity DESC
        """
        return self.conn.execute(sql, params).fetchall()

    def get_mining_summary_by_character(
        self,
        start_date: str | None = None,
        end_date:   str | None = None,
    ) -> list[sqlite3.Row]:
        filters: list[str] = []
        params:  list      = []
        if start_date:
            filters.append("m.mine_date >= ?");  params.append(start_date)
        if end_date:
            filters.append("m.mine_date <= ?");  params.append(end_date)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT  m.character_id,
                    COALESCE(c.character_name, 'Char '||m.character_id) AS character_name,
                    c.corporation_name,
                    SUM(m.quantity)            AS total_quantity,
                    COUNT(DISTINCT m.mine_date) AS active_days,
                    COUNT(DISTINCT m.type_id)   AS ore_types
            FROM    mining_ledger m
            LEFT JOIN characters c ON m.character_id = c.character_id
            {where}
            GROUP BY m.character_id
            ORDER BY total_quantity DESC
        """
        return self.conn.execute(sql, params).fetchall()

    def get_daily_mining_totals(
        self,
        char_ids:   list[int] | None = None,
        start_date: str | None = None,
        end_date:   str | None = None,
    ) -> list[sqlite3.Row]:
        """Returns (mine_date, type_id, total_quantity, unit_volume) grouped by date × type."""
        filters: list[str] = []
        params:  list      = []
        if char_ids:
            ph = ",".join("?" * len(char_ids))
            filters.append(f"m.character_id IN ({ph})")
            params.extend(char_ids)
        if start_date:
            filters.append("m.mine_date >= ?");  params.append(start_date)
        if end_date:
            filters.append("m.mine_date <= ?");  params.append(end_date)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT  m.mine_date,
                    m.type_id,
                    SUM(m.quantity)          AS total_quantity,
                    COALESCE(tc.volume, 0.0) AS unit_volume
            FROM    mining_ledger m
            LEFT JOIN type_cache tc ON m.type_id = tc.type_id
            {where}
            GROUP BY m.mine_date, m.type_id
            ORDER BY m.mine_date
        """
        return self.conn.execute(sql, params).fetchall()

    def get_mining_isk_by_character(
        self,
        char_ids:   list[int] | None = None,
        start_date: str | None = None,
        end_date:   str | None = None,
    ) -> list[sqlite3.Row]:
        """Returns (character_name, type_id, total_quantity) for dashboard ISK computation."""
        filters: list[str] = []
        params:  list      = []
        if char_ids:
            ph = ",".join("?" * len(char_ids))
            filters.append(f"m.character_id IN ({ph})")
            params.extend(char_ids)
        if start_date:
            filters.append("m.mine_date >= ?");  params.append(start_date)
        if end_date:
            filters.append("m.mine_date <= ?");  params.append(end_date)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT  m.character_id,
                    COALESCE(c.character_name, 'Char '||m.character_id) AS character_name,
                    m.type_id,
                    SUM(m.quantity) AS total_quantity
            FROM    mining_ledger m
            LEFT JOIN characters c ON m.character_id = c.character_id
            {where}
            GROUP BY m.character_id, m.type_id
            ORDER BY m.character_id
        """
        return self.conn.execute(sql, params).fetchall()

    # ------------------------------------------------------------------
    # Moon mining (current cycle)
    # ------------------------------------------------------------------

    def save_moon_mining(self, observer_id: int, observer_name: str,
                         entries: list[dict]) -> None:
        """
        Upsert moon mining entries for an observer.
        Automatically detects moon re-pops (quantity decreases) and archives
        the old records to moon_mining_history before overwriting them.
        Each entry must contain: character_id, character_name, recorded_corp_id,
        type_id, type_name, quantity, last_updated.
        """
        now = datetime.utcnow().isoformat()
        with self._lock:
            for e in entries:
                char_id = e.get("character_id")
                type_id = e.get("type_id")
                new_qty = e.get("quantity", 0)

                # Check for moon re-pop (quantity reset)
                existing = self.conn.execute(
                    "SELECT quantity FROM moon_mining WHERE observer_id=? AND character_id=? AND type_id=?",
                    (observer_id, char_id, type_id)
                ).fetchone()
                if existing and existing["quantity"] > new_qty:
                    # Archive old record before overwriting
                    self.conn.execute("""
                        INSERT INTO moon_mining_history
                            (observer_id, observer_name, character_id, character_name,
                             type_id, type_name, quantity, cycle_end_date, archived_at)
                        SELECT observer_id, observer_name, character_id, character_name,
                               type_id, type_name, quantity, last_updated, ?
                        FROM   moon_mining
                        WHERE  observer_id=? AND character_id=? AND type_id=?
                    """, (now, observer_id, char_id, type_id))

                self.conn.execute("""
                    INSERT INTO moon_mining
                        (observer_id, observer_name, character_id, character_name,
                         recorded_corp_id, type_id, type_name, quantity,
                         last_updated, first_recorded)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(observer_id, character_id, type_id) DO UPDATE SET
                        observer_name    = excluded.observer_name,
                        character_name   = excluded.character_name,
                        type_name        = excluded.type_name,
                        quantity         = excluded.quantity,
                        last_updated     = excluded.last_updated
                """, (
                    observer_id, observer_name,
                    char_id, e.get("character_name", ""),
                    e.get("recorded_corp_id"),
                    type_id, e.get("type_name", ""),
                    new_qty, e.get("last_updated", ""),
                    now,
                ))
            self.conn.commit()

    def get_moon_mining(
        self,
        observer_ids: list[int] | None = None,
        start_date:   str | None = None,
        end_date:     str | None = None,
    ) -> list[sqlite3.Row]:
        filters: list[str] = []
        params:  list      = []
        if observer_ids:
            ph = ",".join("?" * len(observer_ids))
            filters.append(f"observer_id IN ({ph})")
            params.extend(observer_ids)
        if start_date:
            filters.append("last_updated >= ?");  params.append(start_date)
        if end_date:
            filters.append("last_updated <= ?");  params.append(end_date)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT mm.*,
                   COALESCE(tc.volume, 0.0)     AS unit_volume,
                   COALESCE(tc.group_name, '')   AS group_name
            FROM   moon_mining mm
            LEFT JOIN type_cache tc ON mm.type_id = tc.type_id
            {where}
            ORDER BY mm.last_updated DESC, mm.character_name, mm.type_name
        """
        return self.conn.execute(sql, params).fetchall()

    def get_moon_mining_history(
        self,
        observer_ids: list[int] | None = None,
    ) -> list[sqlite3.Row]:
        filters: list[str] = []
        params:  list      = []
        if observer_ids:
            ph = ",".join("?" * len(observer_ids))
            filters.append(f"observer_id IN ({ph})")
            params.extend(observer_ids)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        return self.conn.execute(
            f"SELECT * FROM moon_mining_history {where} ORDER BY cycle_end_date DESC, character_name",
            params,
        ).fetchall()

    def get_observers(self) -> list[tuple[int, str]]:
        """Return all known (observer_id, observer_name) pairs from current data."""
        rows = self.conn.execute(
            "SELECT DISTINCT observer_id, observer_name FROM moon_mining ORDER BY observer_name"
        ).fetchall()
        return [(r["observer_id"], r["observer_name"] or f"Observer {r['observer_id']}") for r in rows]

    def get_moon_summary_by_type(
        self,
        observer_ids: list[int] | None = None,
    ) -> list[sqlite3.Row]:
        filters: list[str] = []
        params:  list      = []
        if observer_ids:
            ph = ",".join("?" * len(observer_ids))
            filters.append(f"mm.observer_id IN ({ph})")
            params.extend(observer_ids)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        sql = f"""
            SELECT  mm.type_id,
                    COALESCE(tc.type_name, mm.type_name) AS type_name,
                    COALESCE(tc.group_name, '')           AS group_name,
                    COALESCE(tc.volume, 0.0)              AS unit_volume,
                    SUM(mm.quantity)                      AS total_quantity
            FROM    moon_mining mm
            LEFT JOIN type_cache tc ON mm.type_id = tc.type_id
            {where}
            GROUP BY mm.type_id
            ORDER BY total_quantity DESC
        """
        return self.conn.execute(sql, params).fetchall()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def close(self) -> None:
        if hasattr(self._local, "conn"):
            self._local.conn.close()
