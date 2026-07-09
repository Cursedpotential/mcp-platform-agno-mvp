"""python -m gateway — standalone dev server for the tool gateway."""

import os

import uvicorn

from server.evidence.tool_finder.api import build_app

if __name__ == "__main__":
    uvicorn.run(
        build_app(),
        host=os.getenv("GATEWAY_HOST", "127.0.0.1"),
        port=int(os.getenv("GATEWAY_PORT", "8098")),
    )
