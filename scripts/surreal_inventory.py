"""Read-only inventory of the live SurrealDB: namespaces, databases, tables, counts.

Runs inside the agentos-api container (which already has the surrealdb client and
the credentials in env). Never prints secret values.

Byline: Claude Code - Opus 5 - 2026-08-01
"""

import asyncio
import os

from surrealdb import AsyncSurreal


async def main() -> None:
    url = os.getenv("SURREALDB_URL", "ws://100.119.96.29:8000/rpc")
    ns = os.getenv("SURREALDB_NS", "agno")
    dbname = os.getenv("SURREALDB_DB", "platform")
    print(f"url={url} ns={ns} db={dbname}")

    async with AsyncSurreal(url) as db:
        await db.signin(
            {
                "username": os.getenv("SURREALDB_USER", "root"),
                "password": os.getenv("SURREALDB_PASS", "root"),
            }
        )
        root = await db.query("INFO FOR ROOT;")
        print("NAMESPACES:", list((root or {}).get("namespaces", {}).keys()))

        await db.use(ns, dbname)
        nsinfo = await db.query("INFO FOR NS;")
        print("DATABASES:", list((nsinfo or {}).get("databases", {}).keys()))

        info = await db.query("INFO FOR DB;")
        tables = list((info or {}).get("tables", {}).keys())
        print(f"TABLES in {ns}/{dbname}: {len(tables)}")
        for t in tables:
            try:
                res = await db.query(f"SELECT count() FROM {t} GROUP ALL;")
                n = res[0]["count"] if res else 0
            except Exception as exc:  # noqa: BLE001 - inventory must not abort
                n = f"<{type(exc).__name__}>"
            print(f"  {t}: {n}")


asyncio.run(main())
