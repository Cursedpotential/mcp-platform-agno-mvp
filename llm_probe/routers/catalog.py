from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db
from .. import providers as providers_mod

router = APIRouter(prefix="/providers", tags=["catalog"])


class AddProviderRequest(BaseModel):
    name: str
    base_url: str
    api_key: str
    models_url: Optional[str] = None
    models_auth: str = "bearer"
    supports_penalty_params: Optional[bool] = None


@router.get("")
async def list_providers():
    hardcoded = [
        {"name": name, "configured": p.configured, "base_url": p.base_url,
         "supports_penalty_params": p.supports_penalty_params, "is_custom": False}
        for name, p in providers_mod.PROVIDERS.items()
    ]
    custom = [
        {"name": p["name"], "configured": True, "base_url": p["base_url"],
         "supports_penalty_params": p["supports_penalty_params"], "is_custom": True}
        for p in await db.list_custom_providers()
    ]
    return hardcoded + custom


@router.post("")
async def add_provider(req: AddProviderRequest):
    """Register a new provider. The key is pgcrypto-encrypted at rest
    (llm_eval.custom_provider) and only ever decrypted server-side, in
    memory, at the moment of an outbound call — never returned by any API
    response, never logged."""
    if req.name in providers_mod.PROVIDERS:
        raise HTTPException(409, f"{req.name!r} is one of the built-in providers, can't be overridden")
    await db.add_custom_provider(
        req.name, req.base_url, req.api_key, req.models_url, req.models_auth, req.supports_penalty_params,
    )
    return {"name": req.name, "configured": True, "base_url": req.base_url, "is_custom": True}


@router.delete("/{provider}")
async def delete_provider(provider: str):
    if provider in providers_mod.PROVIDERS:
        raise HTTPException(409, f"{provider!r} is a built-in provider, can't be deleted here")
    await db.delete_custom_provider(provider)
    return {"deleted": provider}


@router.get("/{provider}/models")
async def list_models(provider: str):
    try:
        return await providers_mod.fetch_models(provider)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"failed to fetch catalog from {provider}: {e}")


@router.get("/{provider}/tracked-models")
async def get_tracked_models(provider: str):
    return await db.list_tracked_models(provider)


@router.post("/{provider}/tracked-models/{model:path}")
async def track_model(provider: str, model: str, note: Optional[str] = None):
    await db.add_tracked_model(provider, model, note)
    return {"provider": provider, "model": model, "tracked": True}


@router.delete("/{provider}/tracked-models/{model:path}")
async def untrack_model(provider: str, model: str):
    await db.remove_tracked_model(provider, model)
    return {"provider": provider, "model": model, "tracked": False}


@router.get("/tracked-models/all")
async def all_tracked_models():
    return await db.list_tracked_models()
