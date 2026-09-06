// Byline: Codex · GPT-5 · 2026-08-28 (provider-neutral acquisition routing)
package acquisition

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"

	platformpostgres "github.com/Cursedpotential/probata/engine/postgres"
	"github.com/Cursedpotential/probata/engine/proffer"
)

// NewSchemeRouter combines any number of ImmutableAcquisitionResolver
// values — the local-filesystem resolver from engine/runtimeapi, this
// package's r2/b2 resolvers, and NewUploadIngressResolver — into the one
// ImmutableAcquisitionResolver that engine/postgres.NewSourceLifecycleRepository
// takes. It is the sole place that looks at where a Ref came from
// (its URI scheme); every resolver behind it, and everything downstream of
// retain_original_activity, stays provider-agnostic.
//
// resolvers is keyed by lowercase URI scheme, e.g. {"file": fsResolver,
// "r2": r2Resolver, "b2": b2Resolver, "upload": uploadResolver}. An
// unregistered or unparsable scheme is a closed failure, never a silent
// fallback to some default provider.
func NewSchemeRouter(resolvers map[string]platformpostgres.ImmutableAcquisitionResolver) (platformpostgres.ImmutableAcquisitionResolver, error) {
	if len(resolvers) == 0 {
		return nil, errors.New("acquisition: scheme router requires at least one resolver")
	}
	byScheme := make(map[string]platformpostgres.ImmutableAcquisitionResolver, len(resolvers))
	for scheme, resolver := range resolvers {
		trimmed := strings.ToLower(strings.TrimSpace(scheme))
		if trimmed == "" {
			return nil, errors.New("acquisition: scheme router resolver keys must be non-empty schemes")
		}
		if resolver == nil {
			return nil, fmt.Errorf("acquisition: scheme router resolver for %q is nil", trimmed)
		}
		byScheme[trimmed] = resolver
	}
	return func(ctx context.Context, ref proffer.Ref) (platformpostgres.ImmutableAcquisition, error) {
		if err := ctx.Err(); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		value := strings.TrimSpace(string(ref))
		if value == "" {
			return platformpostgres.ImmutableAcquisition{}, errors.New("acquisition: acquisition reference is empty")
		}
		parsed, err := url.Parse(value)
		if err != nil || parsed.Scheme == "" {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: acquisition reference %q has no URI scheme", value)
		}
		scheme := strings.ToLower(parsed.Scheme)
		resolver, ok := byScheme[scheme]
		if !ok {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: no acquisition resolver registered for scheme %q", scheme)
		}
		return resolver(ctx, ref)
	}, nil
}
