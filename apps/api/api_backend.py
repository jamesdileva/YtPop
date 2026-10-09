"""Frozen backend entry point (D7).

PyInstaller freezes this as `api-backend(.exe)`; the Electron shell spawns it
with `--port <n>`. Argv is uvicorn-compatible (`--host`, `--port`) so dev and
packaged runs share one code path.
"""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="YtPop frozen API backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    # packaged first run: the data dir may be brand new (no migrations run)
    from app.db.database import ensure_schema

    try:
        created = ensure_schema()
    except Exception as e:  # non-fatal: surfaces on the first request instead
        print(f"[api-backend] schema check failed: {e}")
        created = False
    if created:
        print("[api-backend] created missing tables")

    import uvicorn

    # multiprocessing is off: single SQLite writer, packaged-safe
    uvicorn.run("app.main:app", host=args.host, port=args.port,
                workers=1, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
