// Byline: Claude Code · Sonnet (agent) · 2026-07-20
"use client"

/**
 * Hand-rolled on/off switch — deliberately NOT built on a `radix-ui` Switch
 * primitive. Every other primitive in this dir (Dialog, Sheet, Label,
 * Tooltip) imports a namespaced export from the unified `radix-ui` package,
 * but that package's exact bundled primitive set was not verified against
 * this project's pinned version before this file was written (no
 * `node_modules` on the build machine to check against) — a plain
 * `<button role="switch">` needs no new import to resolve, which matters
 * more here than matching the primitive-wrapper pattern exactly.
 */
import * as React from "react"

import { cn } from "@/lib/utils"

interface SwitchProps extends Omit<React.ComponentProps<"button">, "onChange"> {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

function Switch({ checked, onCheckedChange, className, disabled, ...props }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      data-slot="switch"
      data-state={checked ? "checked" : "unchecked"}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-transparent shadow-xs transition-colors outline-none",
        "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-primary" : "bg-input dark:bg-input/80",
        className
      )}
      {...props}
    >
      <span
        data-slot="switch-thumb"
        className={cn(
          "pointer-events-none block size-4 rounded-full bg-background shadow-lg ring-0 transition-transform",
          checked ? "translate-x-4" : "translate-x-0.5"
        )}
      />
    </button>
  )
}

export { Switch }
