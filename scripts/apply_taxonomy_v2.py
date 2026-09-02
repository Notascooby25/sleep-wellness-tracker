#!/usr/bin/env python3
"""Apply the sleep-wellness-tracker taxonomy v2 mapping.

Read-only by default. Requires --apply to write changes. Runs in a single
transaction so any failure rolls the whole change back.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
except ImportError:
    print("ERROR: SQLAlchemy is required. Run this from inside the backend container.", file=sys.stderr)
    raise

logger = logging.getLogger("apply_taxonomy_v2")

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = REPO_ROOT / "db" / "taxonomy_v2.json"
DEFAULT_BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/srv/shared/backups"))
BACKUP_MAX_AGE_MINUTES = int(os.environ.get("BACKUP_MAX_AGE_MINUTES", "60"))
AUDIT_LOG_DIR = Path(os.environ.get("AUDIT_LOG_DIR", str(DEFAULT_BACKUP_DIR)))


@dataclass
class Stats:
    categories_added: int = 0
    activities_added: int = 0
    activities_renamed: int = 0
    activities_deprecated: int = 0
    activities_merged: int = 0
    join_rows_repointed: int = 0
    detail_rows_inserted: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "categories_added": self.categories_added,
            "activities_added": self.activities_added,
            "activities_renamed": self.activities_renamed,
            "activities_deprecated": self.activities_deprecated,
            "activities_merged": self.activities_merged,
            "join_rows_repointed": self.join_rows_repointed,
            "detail_rows_inserted": self.detail_rows_inserted,
        }


def _load_taxonomy(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def _open_audit(apply: bool) -> tuple[Path | None, Any]:
    if not apply:
        return None, None
    AUDIT_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = AUDIT_LOG_DIR / f"taxonomy_v2_apply_{stamp}.jsonl"
    return path, path.open("a", encoding="utf-8")


def _audit(fh, event: str, **fields: Any) -> None:
    if fh is None:
        return
    record = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "event": event, **fields}
    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    fh.flush()


def _require_recent_backup(apply: bool) -> None:
    if not apply:
        return
    if os.environ.get("SKIP_BACKUP_GUARD") == "1":
        logger.warning("Skipping backup guard because SKIP_BACKUP_GUARD=1")
        return
    if not DEFAULT_BACKUP_DIR.exists():
        raise SystemExit(
            f"Refusing to apply: backup directory {DEFAULT_BACKUP_DIR} does not exist. "
            "Run scripts/run_db_backup_rotation.sh first."
        )
    dumps = sorted(DEFAULT_BACKUP_DIR.glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dumps:
        raise SystemExit(
            f"Refusing to apply: no .dump files found in {DEFAULT_BACKUP_DIR}. "
            "Run scripts/run_db_backup_rotation.sh first."
        )
    newest = dumps[0]
    age_minutes = (time.time() - newest.stat().st_mtime) / 60.0
    if age_minutes > BACKUP_MAX_AGE_MINUTES:
        raise SystemExit(
            f"Refusing to apply: newest backup {newest.name} is {age_minutes:.1f} minutes old "
            f"(max {BACKUP_MAX_AGE_MINUTES}). Run scripts/run_db_backup_rotation.sh."
        )
    logger.info("Backup guard OK: %s age=%.1f min", newest.name, age_minutes)


def _get_category_id(conn, name: str) -> int | None:
    row = conn.execute(text("SELECT id FROM categories WHERE name = :name"), {"name": name}).fetchone()
    return row[0] if row else None


def _ensure_category(conn, name: str, apply: bool, stats: Stats, audit) -> int | None:
    existing = _get_category_id(conn, name)
    if existing is not None:
        return existing
    stats.categories_added += 1
    if not apply:
        logger.info("[dry-run] would create category: %s", name)
        return None
    row = conn.execute(
        text("INSERT INTO categories (name, require_rating) VALUES (:name, 1) RETURNING id"),
        {"name": name},
    ).fetchone()
    _audit(audit, "category_added", name=name, id=row[0])
    return row[0]


def _get_activity(conn, name: str, category_id: int | None = None):
    if category_id is not None:
        return conn.execute(
            text("SELECT id, category_id, deprecated_at FROM activities WHERE name = :name AND category_id = :cid"),
            {"name": name, "cid": category_id},
        ).fetchone()
    return conn.execute(
        text("SELECT id, category_id, deprecated_at FROM activities WHERE name = :name"),
        {"name": name},
    ).fetchone()


def _ensure_activity(conn, name: str, category_id: int | None, apply: bool, stats: Stats, audit):
    row = _get_activity(conn, name, category_id)
    if row is not None:
        return row[0]
    stats.activities_added += 1
    if not apply:
        logger.info("[dry-run] would create activity: %s (category_id=%s)", name, category_id)
        return None
    result = conn.execute(
        text(
            "INSERT INTO activities (name, category_id, is_archived) "
            "VALUES (:name, :cid, FALSE) RETURNING id"
        ),
        {"name": name, "cid": category_id},
    ).fetchone()
    _audit(audit, "activity_added", name=name, category_id=category_id, id=result[0])
    return result[0]


def _rename_activity(conn, old: str, new: str, apply: bool, stats: Stats, audit) -> None:
    row_old = _get_activity(conn, old)
    if row_old is None:
        return
    # Ignore deprecated targets so we don't merge historical entries into a stale duplicate.
    row_new = conn.execute(
        text("SELECT id FROM activities WHERE name = :name AND deprecated_at IS NULL"),
        {"name": new},
    ).fetchone()
    if row_new is not None and row_new[0] != row_old[0]:
        _merge_activity(conn, old_id=row_old[0], into_id=row_new[0], position=None, apply=apply, stats=stats, audit=audit)
        return
    stats.activities_renamed += 1
    if not apply:
        logger.info("[dry-run] would rename activity: %s -> %s", old, new)
        return
    conn.execute(text("UPDATE activities SET name = :new WHERE id = :id"), {"new": new, "id": row_old[0]})
    _audit(audit, "activity_renamed", old=old, new=new, id=row_old[0])


def _merge_activity(conn, old_id: int, into_id: int, position: str | None, apply: bool, stats: Stats, audit) -> None:
    if old_id == into_id:
        return
    join_rows = conn.execute(
        text("SELECT mood_id FROM mood_activities WHERE activity_id = :old"),
        {"old": old_id},
    ).fetchall()
    mood_ids = [r[0] for r in join_rows]
    if not apply:
        logger.info(
            "[dry-run] would repoint %d mood link(s) from activity_id=%s into %s with position=%s",
            len(mood_ids), old_id, into_id, position,
        )
        stats.join_rows_repointed += len(mood_ids)
        stats.activities_deprecated += 1
        stats.activities_merged += 1
        if position is not None:
            stats.detail_rows_inserted += len(mood_ids)
        return
    for mood_id in mood_ids:
        exists_new = conn.execute(
            text("SELECT 1 FROM mood_activities WHERE mood_id = :m AND activity_id = :a"),
            {"m": mood_id, "a": into_id},
        ).fetchone()
        if exists_new is None:
            conn.execute(
                text("INSERT INTO mood_activities (mood_id, activity_id) VALUES (:m, :a)"),
                {"m": mood_id, "a": into_id},
            )
        conn.execute(
            text("DELETE FROM mood_activities WHERE mood_id = :m AND activity_id = :a"),
            {"m": mood_id, "a": old_id},
        )
        stats.join_rows_repointed += 1
        if position is not None:
            already = conn.execute(
                text(
                    "SELECT 1 FROM mood_activity_details "
                    "WHERE mood_id = :m AND activity_id = :a AND position = :p"
                ),
                {"m": mood_id, "a": into_id, "p": position},
            ).fetchone()
            if already is None:
                conn.execute(
                    text(
                        "INSERT INTO mood_activity_details (mood_id, activity_id, position) "
                        "VALUES (:m, :a, :p)"
                    ),
                    {"m": mood_id, "a": into_id, "p": position},
                )
                stats.detail_rows_inserted += 1
    conn.execute(
        text("UPDATE activities SET deprecated_at = COALESCE(deprecated_at, NOW()) WHERE id = :id"),
        {"id": old_id},
    )
    stats.activities_deprecated += 1
    stats.activities_merged += 1
    _audit(
        audit,
        "activity_merged",
        old_id=old_id,
        into_id=into_id,
        position=position,
        moods_repointed=len(mood_ids),
    )


def _deprecate_activity(conn, category_id: int | None, name: str, apply: bool, stats: Stats, audit) -> None:
    row = _get_activity(conn, name, category_id)
    if row is None or row[2] is not None:
        return
    stats.activities_deprecated += 1
    if not apply:
        logger.info("[dry-run] would deprecate activity: %s (category_id=%s)", name, category_id)
        return
    conn.execute(
        text("UPDATE activities SET deprecated_at = NOW() WHERE id = :id"),
        {"id": row[0]},
    )
    _audit(audit, "activity_deprecated", name=name, category_id=category_id, id=row[0])


def _apply_all(conn, taxonomy: dict[str, Any], apply: bool, stats: Stats, audit) -> None:
    category_ids: dict[str, int | None] = {}
    for name in taxonomy.get("categories", []):
        category_ids[name] = _ensure_category(conn, name, apply, stats, audit)

    for item in taxonomy.get("activities_add", []):
        cat = category_ids.get(item["category"])
        _ensure_activity(conn, item["name"], cat, apply, stats, audit)

    for item in taxonomy.get("activities_deprecate", []):
        cat = category_ids.get(item.get("category")) if item.get("category") else None
        _deprecate_activity(conn, cat, item["name"], apply, stats, audit)

    for item in taxonomy.get("activities_rename", []):
        _rename_activity(conn, item["from"], item["to"], apply, stats, audit)

    for group in taxonomy.get("activities_merge", []):
        into_name = group["into"]["name"]
        into_cat = category_ids.get(group["into"]["category"])
        into_id = _ensure_activity(conn, into_name, into_cat, apply, stats, audit)
        for src in group["from"]:
            src_row = _get_activity(conn, src["name"])
            if src_row is None:
                continue
            if into_id is None:
                logger.info("[dry-run] would merge %s into %s (position=%s)", src["name"], into_name, src.get("position"))
                stats.activities_merged += 1
                continue
            _merge_activity(
                conn,
                old_id=src_row[0],
                into_id=into_id,
                position=src.get("position"),
                apply=apply,
                stats=stats,
                audit=audit,
            )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run.")
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY_PATH, help="Path to taxonomy JSON.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )

    taxonomy = _load_taxonomy(args.taxonomy)
    logger.info("Loaded taxonomy version=%s", taxonomy.get("version"))

    _require_recent_backup(apply=args.apply)

    engine: Engine = create_engine(_database_url(), future=True)
    stats = Stats()
    audit_path, audit_fh = _open_audit(apply=args.apply)

    try:
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                _apply_all(conn, taxonomy, apply=args.apply, stats=stats, audit=audit_fh)
                if args.apply:
                    trans.commit()
                else:
                    trans.rollback()
                    logger.info("Dry-run complete; changes rolled back.")
            except Exception:
                trans.rollback()
                raise
    finally:
        if audit_fh is not None:
            audit_fh.close()

    logger.info("Stats: %s", json.dumps(stats.as_dict()))
    if audit_path is not None:
        logger.info("Audit log: %s", audit_path)
    if not args.apply:
        logger.info("No changes were written. Re-run with --apply to persist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
