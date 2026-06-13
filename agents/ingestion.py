"""Knowledge ingestion entrypoint — run inside the container:

    docker exec agentos-api python -m agents.ingestion
"""

import asyncio

from scripts.ingest_knowledge import main

if __name__ == "__main__":
    asyncio.run(main())
