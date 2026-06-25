"""Minimal sandboxed exec API for agents.

POST /run  {"language": "python"|"node"|"bash", "code": "...", "timeout": 30}
->         {"stdout": ..., "stderr": ..., "exit_code": ..., "timed_out": bool}

Runs as non-root in an isolated container with no secrets and no host mounts.
Hard caps: 60s timeout ceiling, 1MB output per stream.
"""

import asyncio
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="agent-sandbox")

MAX_TIMEOUT = 60
MAX_OUTPUT = 1_000_000

RUNNERS = {
    "python": ["python", "{file}"],
    "node": ["node", "{file}"],
    "bash": ["bash", "{file}"],
}
SUFFIX = {"python": ".py", "node": ".js", "bash": ".sh"}


class RunRequest(BaseModel):
    language: str = "python"
    code: str
    timeout: int = 30


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/run")
async def run(req: RunRequest):
    if req.language not in RUNNERS:
        return {"error": f"language must be one of {sorted(RUNNERS)}"}
    timeout = min(max(req.timeout, 1), MAX_TIMEOUT)
    with tempfile.NamedTemporaryFile("w", suffix=SUFFIX[req.language], dir="/workspace", delete=False) as f:
        f.write(req.code)
        path = f.name
    try:
        cmd = [a.format(file=path) for a in RUNNERS[req.language]]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/workspace",
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            timed_out = False
        except asyncio.TimeoutError:
            proc.kill()
            out, err = b"", b"(killed: timeout)"
            timed_out = True
        return {
            "stdout": out[:MAX_OUTPUT].decode(errors="replace"),
            "stderr": err[:MAX_OUTPUT].decode(errors="replace"),
            "exit_code": proc.returncode,
            "timed_out": timed_out,
        }
    finally:
        Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8070)
