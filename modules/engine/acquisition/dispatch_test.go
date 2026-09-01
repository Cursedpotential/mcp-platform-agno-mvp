// Byline: Codex · GPT-5 · 2026-08-28 (acquisition routing tests)
package acquisition

import (
	"context"
	"testing"

	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/stretchr/testify/require"
)

func constResolver(result platformpostgres.ImmutableAcquisition, err error) platformpostgres.ImmutableAcquisitionResolver {
	return func(context.Context, uiw.Ref) (platformpostgres.ImmutableAcquisition, error) {
		return result, err
	}
}

func TestSchemeRouterDispatchesByScheme(t *testing.T) {
	fsResult := platformpostgres.ImmutableAcquisition{StorageClass: "filesystem", ByteLength: 1}
	r2Result := platformpostgres.ImmutableAcquisition{StorageClass: storageClassSealed, ByteLength: 2}
	uploadResult := platformpostgres.ImmutableAcquisition{StorageClass: storageClassSealed, ByteLength: 3}

	router, err := NewSchemeRouter(map[string]platformpostgres.ImmutableAcquisitionResolver{
		"file":   constResolver(fsResult, nil),
		"r2":     constResolver(r2Result, nil),
		"upload": constResolver(uploadResult, nil),
	})
	require.NoError(t, err)

	got, err := router(context.Background(), "file:///tmp/x.bin")
	require.NoError(t, err)
	require.Equal(t, fsResult, got)

	got, err = router(context.Background(), CloudflareR2Ref("bucket", "key"))
	require.NoError(t, err)
	require.Equal(t, r2Result, got)

	got, err = router(context.Background(), uiw.Ref("upload://"+"ab"))
	require.NoError(t, err)
	require.Equal(t, uploadResult, got)
}

func TestSchemeRouterRejectsUnregisteredScheme(t *testing.T) {
	router, err := NewSchemeRouter(map[string]platformpostgres.ImmutableAcquisitionResolver{
		"file": constResolver(platformpostgres.ImmutableAcquisition{}, nil),
	})
	require.NoError(t, err)

	_, err = router(context.Background(), BackblazeB2Ref("bucket", "key"))
	require.Error(t, err)
	require.Contains(t, err.Error(), `"b2"`)
}

func TestSchemeRouterRejectsSchemelessOrEmptyRef(t *testing.T) {
	router, err := NewSchemeRouter(map[string]platformpostgres.ImmutableAcquisitionResolver{
		"file": constResolver(platformpostgres.ImmutableAcquisition{}, nil),
	})
	require.NoError(t, err)

	_, err = router(context.Background(), "")
	require.Error(t, err)
	_, err = router(context.Background(), "no-scheme-here")
	require.Error(t, err)
}

func TestSchemeRouterRejectsEmptyOrNilResolverSet(t *testing.T) {
	_, err := NewSchemeRouter(nil)
	require.Error(t, err)

	_, err = NewSchemeRouter(map[string]platformpostgres.ImmutableAcquisitionResolver{"file": nil})
	require.Error(t, err)
}
