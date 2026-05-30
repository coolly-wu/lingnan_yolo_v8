"""本地台账：检测日志 SQLite 持久化

依据技术规范 §8.9.1 detection_log 表结构。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .. import config as C


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS detection_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    datetime TEXT NOT NULL,
    sample_source TEXT NOT NULL,
    target_disease TEXT NOT NULL,
    confidence REAL NOT NULL,
    severity_level TEXT NOT NULL,
    count_value INTEGER NOT NULL DEFAULT 0,
    farmer_name TEXT DEFAULT '',
    orchard_block TEXT DEFAULT '',
    phenophase TEXT DEFAULT '',
    prescription_snapshot TEXT DEFAULT '',
    image_path TEXT DEFAULT '',
    annotated_path TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_log_datetime ON detection_log(datetime);
CREATE INDEX IF NOT EXISTS idx_log_farmer   ON detection_log(farmer_name);
CREATE INDEX IF NOT EXISTS idx_log_disease  ON detection_log(target_disease);
"""


class LogManager:
    """检测台账管理"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or C.RUNTIME_LOG_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA_SQL)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def insert(self, *, sample_source: str, target_disease: str, confidence: float,
               severity_level: str, count_value: int = 0,
               farmer_name: str = "", orchard_block: str = "",
               phenophase: str = "", prescription_snapshot: dict | list | None = None,
               image_path: str = "", annotated_path: str = "",
               notes: str = "") -> int:
        snap = ""
        if prescription_snapshot is not None:
            try:
                snap = json.dumps(prescription_snapshot, ensure_ascii=False)
            except Exception:
                snap = str(prescription_snapshot)
        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._conn() as c:
            cur = c.execute(
                """INSERT INTO detection_log
                (datetime, sample_source, target_disease, confidence, severity_level,
                 count_value, farmer_name, orchard_block, phenophase,
                 prescription_snapshot, image_path, annotated_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (dt, sample_source, target_disease, confidence, severity_level,
                 count_value, farmer_name, orchard_block, phenophase,
                 snap, image_path, annotated_path, notes),
            )
            return int(cur.lastrowid)

    def query(self, *, start: str | None = None, end: str | None = None,
              farmer: str | None = None, disease: str | None = None,
              limit: int = 5000) -> list[dict]:
        sql = "SELECT * FROM detection_log WHERE 1=1"
        args: list = []
        if start:
            sql += " AND datetime >= ?"
            args.append(start)
        if end:
            sql += " AND datetime <= ?"
            args.append(end)
        if farmer:
            sql += " AND farmer_name LIKE ?"
            args.append(f"%{farmer}%")
        if disease:
            sql += " AND target_disease = ?"
            args.append(disease)
        sql += " ORDER BY datetime DESC LIMIT ?"
        args.append(int(limit))
        with self._conn() as c:
            rows = c.execute(sql, args).fetchall()
            return [dict(r) for r in rows]

    def delete_all(self) -> int:
        with self._conn() as c:
            cur = c.execute("DELETE FROM detection_log")
            return cur.rowcount

    def count(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM detection_log").fetchone()[0])
