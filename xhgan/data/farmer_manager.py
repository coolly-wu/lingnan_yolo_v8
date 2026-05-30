"""农户 / 果园档案：SQLite 持久化"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .. import config as C


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS farmer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_name TEXT NOT NULL,
    orchard_block TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    location TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_farmer_name_block
    ON farmer(farmer_name, orchard_block);
"""


CSV_FIELDS = ["农户姓名", "果园区块", "联系电话", "果园位置", "备注"]
REQUIRED_CSV_FIELDS = ["农户姓名", "果园区块", "联系电话", "果园位置"]
CSV_FIELD_ALIASES = {
    "农户姓名": "farmer_name",
    "farmer_name": "farmer_name",
    "姓名": "farmer_name",
    "果园区块": "orchard_block",
    "orchard_block": "orchard_block",
    "区块": "orchard_block",
    "联系电话": "phone",
    "电话": "phone",
    "phone": "phone",
    "果园位置": "location",
    "位置": "location",
    "location": "location",
    "备注": "notes",
    "notes": "notes",
}
CSV_REQUIRED_KEYS = ["farmer_name", "orchard_block", "phone", "location"]
CSV_EXAMPLE_ROW = {
    "农户姓名": "张三",
    "果园区块": "A-1",
    "联系电话": "13800000000",
    "果园位置": "廉江市某镇某村",
    "备注": "示例：5亩廉江红橙园",
}


@dataclass
class FarmerCsvImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return self.imported


class FarmerManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or C.RUNTIME_LOG_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA_SQL)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def list_all(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM farmer ORDER BY farmer_name, orchard_block"
            ).fetchall()
            return [dict(r) for r in rows]

    def insert(self, *, farmer_name: str, orchard_block: str = "",
               phone: str = "", location: str = "", notes: str = "") -> int:
        if not farmer_name.strip():
            raise ValueError("农户姓名不能为空")
        with self._conn() as c:
            cur = c.execute(
                """INSERT OR REPLACE INTO farmer
                   (farmer_name, orchard_block, phone, location, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (farmer_name.strip(), orchard_block.strip(),
                 phone.strip(), location.strip(), notes.strip()),
            )
            return int(cur.lastrowid)

    def update(self, record_id: int, **fields) -> None:
        if not fields:
            return
        cols, vals = [], []
        for k, v in fields.items():
            if k in {"farmer_name", "orchard_block", "phone", "location", "notes"}:
                cols.append(f"{k}=?")
                vals.append(v.strip() if isinstance(v, str) else v)
        if not cols:
            return
        vals.append(record_id)
        with self._conn() as c:
            c.execute(f"UPDATE farmer SET {', '.join(cols)} WHERE id=?", vals)

    def delete(self, record_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM farmer WHERE id=?", (record_id,))

    def count(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM farmer").fetchone()[0])

    def write_csv_template(self, path: str | Path) -> Path:
        """写出 Excel 友好的农户档案导入模板。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerow(CSV_EXAMPLE_ROW)
        return target

    def import_csv(self, path: str | Path) -> FarmerCsvImportResult:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"CSV 文件不存在：{source}")

        result = FarmerCsvImportResult()
        with source.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV 文件缺少表头")

            header_map = self._build_csv_header_map(reader.fieldnames)
            missing = [name for name in REQUIRED_CSV_FIELDS
                       if CSV_FIELD_ALIASES[name] not in header_map]
            if missing:
                raise ValueError("CSV 缺少必填列：" + "、".join(missing))

            for line_no, raw in enumerate(reader, start=2):
                normalized = self._normalize_csv_row(raw, header_map)
                if not any(normalized.values()):
                    result.skipped += 1
                    continue

                empty_required = [
                    field for field in CSV_REQUIRED_KEYS
                    if not normalized.get(field, "").strip()
                ]
                if empty_required:
                    result.skipped += 1
                    result.errors.append(
                        f"第 {line_no} 行缺少必填字段："
                        + "、".join(self._csv_display_name(k) for k in empty_required)
                    )
                    continue

                self.insert(
                    farmer_name=normalized["farmer_name"],
                    orchard_block=normalized["orchard_block"],
                    phone=normalized["phone"],
                    location=normalized["location"],
                    notes=normalized.get("notes", ""),
                )
                result.imported += 1

        return result

    @staticmethod
    def _build_csv_header_map(fieldnames: list[str]) -> dict[str, str]:
        header_map: dict[str, str] = {}
        for field in fieldnames:
            name = (field or "").strip()
            key = CSV_FIELD_ALIASES.get(name)
            if key and key not in header_map:
                header_map[key] = field
        return header_map

    @staticmethod
    def _normalize_csv_row(raw: dict[str, str], header_map: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, source_name in header_map.items():
            normalized[key] = (raw.get(source_name) or "").strip()
        return normalized

    @staticmethod
    def _csv_display_name(key: str) -> str:
        names = {
            "farmer_name": "农户姓名",
            "orchard_block": "果园区块",
            "phone": "联系电话",
            "location": "果园位置",
            "notes": "备注",
        }
        return names.get(key, key)
