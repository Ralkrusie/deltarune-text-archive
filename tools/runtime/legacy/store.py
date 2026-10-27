"""Transactional, idempotent import for the source/consumer pilot (schema 1)."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def import_log(database: Path, log: Path, sources: Path) -> dict:
    initial_header=json.loads(log.read_bytes().splitlines()[0])
    sources=resolve_sources(sources,initial_header.get('source_manifest'))
    manifest_hash = hashlib.sha256(sources.read_bytes()).hexdigest()
    inventory = json.loads(sources.read_text(encoding="utf-8"))
    if inventory.get("schema") != 1:
        raise ValueError("Unknown inventory schema")
    by_id = {r["source_id"]: r for r in inventory["sources"]}
    if len(by_id) != len(inventory["sources"]):
        raise ValueError("Duplicate source ID")
    raw = log.read_bytes()
    # Only a final, non-terminated line can be incomplete. Interior errors reject all.
    lines = raw.splitlines(keepends=True)
    tail_incomplete = bool(lines and not lines[-1].endswith(b"\n"))
    if tail_incomplete:
        lines.pop()
    if not lines:
        raise ValueError("Missing complete header")
    records = [json.loads(line) for line in lines]
    header = records[0]
    if header.get('schema') == 2:
        if header.get('source_manifest') != manifest_hash: raise ValueError('Source inventory mismatch')
        from .store_v2 import import_v2
        return import_v2(database,records,inventory,tail_incomplete)
    if (header.get("kind") != "header" or header.get("schema") != 1
            or header.get("source_manifest") != manifest_hash
            or header.get("mode") != "natural_play_pilot"):
        raise ValueError("Header/schema/source binding mismatch")
    session = header["session_id"]
    if not isinstance(session, str) or len(session) != 32 or any(c not in "0123456789abcdef" for c in session):
        raise ValueError("Invalid session ID")
    prepared = []
    for n, record in enumerate(records[1:], 1):
        if record.get("kind") != "observation" or record.get("seq") != n:
            raise ValueError("Unknown record kind or missing/reordered sequence")
        sid = record.get("source_id")
        if type(sid) not in (int, float) or sid != int(sid) or sid < 0:
            raise ValueError("Invalid source ID")
        source = by_id.get(int(sid))
        if sid and source is None:
            raise ValueError("Unknown source ID; refuse first-key matching")
        if record.get("language") != "en" or record.get("stage") != "draw_enter" or record.get("partial") is not True:
            raise ValueError("Unsupported observation capability")
        room = record.get("room_name", record.get("room"))
        if not isinstance(record.get("text"), str) or (room is not None and not isinstance(room, str)):
            raise ValueError("Invalid text/context")
        # The event is a partial draw-entry observation. No speaker/style inference.
        body = {"schema": 1, "manifest": manifest_hash,
                "occurrence_id": source["occurrence_id"] if source else None,
                "binding": "propagated_source_tag" if source else "unmatched",
                "language": "en", "room": room, "channel": record["channel"],
                "text": record["text"], "stage": record["stage"], "partial": True,
                "io_failed": bool(record.get("io_failed")),
                "fields": {k: "not_instrumented" for k in ("identity", "assets", "color", "motion", "relations")}}
        prepared.append((n, record, body, digest(body)))
    database.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database)
    try:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables:
            if "meta" not in tables or db.execute("SELECT value FROM meta WHERE key='schema'").fetchone() != ("capture-pilot-1",):
                raise ValueError("Refusing to modify an unrelated database")
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sources (manifest TEXT NOT NULL, source_id INTEGER NOT NULL,
            occurrence_id TEXT NOT NULL, body TEXT NOT NULL, PRIMARY KEY(manifest,source_id));
        CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, header TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS variants (variant_id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS observations (session_id TEXT NOT NULL REFERENCES sessions,
            seq INTEGER NOT NULL, variant_id TEXT NOT NULL REFERENCES variants,
            raw TEXT NOT NULL, PRIMARY KEY(session_id,seq));
        """)
        with db:
            version = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            if version and version[0] != "capture-pilot-1":
                raise ValueError("Incompatible database")
            db.execute("INSERT OR IGNORE INTO meta VALUES ('schema','capture-pilot-1')")
            existing = db.execute("SELECT header FROM sessions WHERE session_id=?", (session,)).fetchone()
            if existing and existing[0] != canonical(header):
                raise ValueError("Session identity reused with a different header")
            db.execute("INSERT OR IGNORE INTO sessions VALUES (?,?)", (session, canonical(header)))
            for source in inventory["sources"]:
                db.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?,?)",
                           (manifest_hash, source["source_id"], source["occurrence_id"], canonical(source)))
            new_observations = new_variants = 0
            for seq, record, body, vid in prepared:
                previous = db.execute("SELECT raw FROM observations WHERE session_id=? AND seq=?", (session, seq)).fetchone()
                if previous:
                    if previous[0] != canonical(record):
                        raise ValueError("Previously imported event was altered")
                    continue
                new_variants += db.execute("INSERT OR IGNORE INTO variants VALUES (?,?)", (vid, canonical(body))).rowcount
                db.execute("INSERT INTO observations VALUES (?,?,?,?)", (session, seq, vid, canonical(record)))
                new_observations += 1
        return {"session_id": session, "events": len(prepared), "new_observations": new_observations,
                "new_variants": new_variants, "unmatched": sum(b["occurrence_id"] is None for _,_,b,_ in prepared),
                "missing_room": sum(b["room"] is None for _,_,b,_ in prepared),
                "tail_incomplete": tail_incomplete, "capture_complete": False}
    finally:
        db.close()


def resolve_sources(sources:Path, expected:str):
    if hashlib.sha256(sources.read_bytes()).hexdigest()==expected:return sources
    if not isinstance(expected,str) or len(expected)!=64 or any(c not in 'abcdef0123456789' for c in expected):raise ValueError('Invalid inventory digest')
    archived=sources.parent/'inventories'/(expected+'.json')
    if archived.exists() and hashlib.sha256(archived.read_bytes()).hexdigest()==expected:return archived
    raise ValueError('Source inventory not found for this log')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(import_log(args.db, args.log, args.sources), indent=2))
