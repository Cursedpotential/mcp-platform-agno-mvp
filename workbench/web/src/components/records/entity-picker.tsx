// Byline: Codex · GPT-5 · 2026-08-18 (governed entity search/select/create)
"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, createGovernedEntity, listGovernedEntities } from "@/lib/api-client";
import type { GovernedEntity } from "@/lib/shared/types";

interface EntityPickerProps {
  label: string;
  rawIdentity?: string | null;
  value: string;
  disabled?: boolean;
  onChange: (entityId: string) => void;
}

export function EntityPicker({ label, rawIdentity, value, disabled, onChange }: EntityPickerProps) {
  const [query, setQuery] = useState(rawIdentity ?? "");
  const [entities, setEntities] = useState<GovernedEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [entityType, setEntityType] = useState("person");

  const search = async (nextQuery = query) => {
    setLoading(true);
    try {
      const result = await listGovernedEntities(nextQuery);
      setEntities(result.entities);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Entity search failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    queueMicrotask(() => {
      setQuery(rawIdentity ?? "");
      void search(rawIdentity ?? "");
    });
    // The raw identity is the intentional reset boundary for this picker.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawIdentity]);

  const create = async () => {
    const displayName = query.trim();
    if (!displayName) return;
    setLoading(true);
    try {
      const entity = await createGovernedEntity({ display_name: displayName, entity_type: entityType });
      setEntities((current) => [entity, ...current.filter((item) => item.id !== entity.id)]);
      onChange(entity.id);
      toast.success(`Created and selected ${entity.display_name}`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Entity creation failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-1.5 rounded-md border p-2">
      <p className="text-xs font-medium">{label}: {rawIdentity || "missing raw identity"}</p>
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void search();
            }
          }}
          placeholder="Search people and aliases"
          aria-label={`Search entity for ${label}`}
          disabled={disabled}
        />
        <Button type="button" variant="outline" onClick={() => void search()} disabled={disabled || loading}>
          Search
        </Button>
      </div>
      <select
        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={`Select entity for ${label}`}
        disabled={disabled}
      >
        <option value="">— select a governed entity —</option>
        {entities.map((entity) => (
          <option key={entity.id} value={entity.id}>
            {entity.display_name} · {entity.entity_type} · {entity.review_status}
          </option>
        ))}
      </select>
      <div className="flex gap-2">
        <select
          className="flex h-8 rounded-md border border-input bg-transparent px-2 text-xs"
          value={entityType}
          onChange={(event) => setEntityType(event.target.value)}
          aria-label={`New entity type for ${label}`}
          disabled={disabled}
        >
          <option value="person">Person</option><option value="phone">Phone</option><option value="email">Email</option>
          <option value="handle">Handle</option><option value="account">Account</option><option value="device">Device</option>
          <option value="org">Organization</option><option value="institution">Institution</option><option value="platform">Platform</option>
        </select>
        <Button type="button" size="sm" variant="secondary" onClick={create} disabled={disabled || loading || !query.trim()}>
          Create “{query.trim() || "new entity"}”
        </Button>
      </div>
    </div>
  );
}
