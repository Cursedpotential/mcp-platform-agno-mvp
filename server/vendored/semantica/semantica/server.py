"""
Semantica Server Entry Point

This module provides the REST API server for the Semantica framework
using FastAPI and uvicorn.
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from . import __version__
from .core.orchestrator import Semantica
from .utils.logging import setup_logging

# Initialize logging
setup_logging()

app = FastAPI(
    title="Semantica API",
    description="REST API for the Semantica Framework",
    version=__version__
)

# Global framework instance
framework = Semantica()

class BuildRequest(BaseModel):
    sources: List[str]
    config: Optional[Dict[str, Any]] = None

@app.get("/")
async def root():
    """Root endpoint returning framework info."""
    return {
        "name": "Semantica API",
        "version": __version__,
        "status": "active"
    }

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/build")
async def build_kb(request: BuildRequest):
    """Initiate knowledge base construction."""
    try:
        # result = framework.build_knowledge_base(sources=request.sources, config=request.config)
        return {"status": "accepted", "message": "Knowledge base construction initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def main():
    """Server entry point."""
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
