"""SQLite 知识库：12 类病虫害 × 5 物候期 三位一体绿色防治方案

依据技术规范 §8.8 与 §8.9：
  prescription 表：(disease_id, phenophase) 复合索引
  字段：physical / biological / chemical / severity_amplifier
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import config as C
from . import prescriptions_seed as seed


# ---------- 表结构 ----------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS prescription (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease_id INTEGER NOT NULL,
    disease_name_cn TEXT NOT NULL,
    phenophase_key TEXT NOT NULL,
    phenophase_name_cn TEXT NOT NULL,
    physical TEXT NOT NULL,
    biological TEXT NOT NULL,
    chemical TEXT NOT NULL,                 -- JSON: [{name, dosage, phi, notes}, ...]
    severity_amplifier TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_disease_phenophase
    ON prescription(disease_id, phenophase_key);
"""


class KnowledgeBase:
    """病虫害绿色防治知识库"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or C.KNOWLEDGE_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._conn() as c:
            c.executescript(SCHEMA_SQL)
            # 仅在表空时种入初始方案
            cur = c.execute("SELECT COUNT(*) FROM prescription")
            if cur.fetchone()[0] == 0:
                self._seed(c)

    def _seed(self, c: sqlite3.Connection):
        for row in seed.iter_seed_rows():
            c.execute(
                """INSERT OR IGNORE INTO prescription
                   (disease_id, disease_name_cn, phenophase_key, phenophase_name_cn,
                    physical, biological, chemical, severity_amplifier)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["disease_id"],
                    row["disease_name_cn"],
                    row["phenophase_key"],
                    row["phenophase_name_cn"],
                    row["physical"],
                    row["biological"],
                    json.dumps(row["chemical"], ensure_ascii=False),
                    row.get("severity_amplifier", ""),
                ),
            )

    # ---------- 对外查询 ----------
    def lookup(self, disease_id: int, phenophase_key: str) -> dict | None:
        with self._conn() as c:
            cur = c.execute(
                """SELECT * FROM prescription
                   WHERE disease_id=? AND phenophase_key=?""",
                (disease_id, phenophase_key),
            )
            r = cur.fetchone()
            if r is None:
                # fallback 至任意物候期
                cur = c.execute(
                    "SELECT * FROM prescription WHERE disease_id=? LIMIT 1",
                    (disease_id,),
                )
                r = cur.fetchone()
            if r is None:
                return None
            d = dict(r)
            try:
                d["chemical"] = json.loads(d["chemical"])
            except Exception:
                d["chemical"] = []
            return d

    def count(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM prescription").fetchone()[0])
