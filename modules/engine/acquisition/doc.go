// Byline: Codex · GPT-5 · 2026-08-28 (provider-neutral acquisition boundary)
// Package acquisition implements the provider-neutral object acquisition
// boundary for the Universal Import Workflow: it turns an opaque proffer.Ref
// naming a not-yet-retained source — a Cloudflare R2 object, a Backblaze B2
// object, or a bearer-authenticated Windows upload — into exactly the same
// platformpostgres.ImmutableAcquisition that retain_original_activity
// (engine/activities.SourceLifecycleActivities.RetainOriginal via
// engine/postgres.SourceLifecycleRepository) already consumes from the
// local-filesystem resolver in engine/runtimeapi/acquisition_resolver.go.
//
// Every resolver in this package funnels through the single sealStream
// primitive in seal.go, which stages, hashes, and content-addresses bytes
// into the same objects/sha256/<xx>/<hex>.source layout the filesystem
// resolver uses. Pointing two resolvers at the same root directory therefore
// deduplicates acquisitions across origins for free: an R2 object and an
// uploaded file with identical bytes publish to the identical object path.
//
// No Activity, workflow stage, or downstream store ever branches on which
// provider resolved a source — every resolver returns the identical
// ImmutableAcquisition shape, and NewSchemeRouter (dispatch.go) is the only
// place that looks at where a Ref came from. That keeps register_source and
// retain_original activity bodies, and everything after them, completely
// provider-agnostic.
//
// This package intentionally does not import engine/runtimeapi: it is a
// deliberately isolated acquisition boundary so it can be reviewed, tested,
// and landed without touching files other concurrent lanes are editing. The
// staging/publish/verify pattern here mirrors
// engine/runtimeapi/acquisition_resolver.go by design, not by import.
package acquisition
