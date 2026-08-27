from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import providers as providers_mod

router = APIRouter(prefix="/providers", tags=["catalog"])


@router.get("")
async def list_providers():
    return [
        {"name": name, "configured": p.configured, "base_url": p.base_url}
        for name, p in providers_mod.PROVIDERS.items()
    ]


@router.get("/{provider}/models")
async def list_models(provider: str):
    try:
        return await providers_mod.fetch_models(provider)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"failed to fetch catalog from {provider}: {e}")
