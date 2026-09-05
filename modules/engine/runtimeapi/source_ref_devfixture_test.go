// Byline: Claude Code · Fable 5.1 · 2026-09-05 — regression for the live 422
// "source_ref must be an upload reference or a Case Bible Sorted object" on
// the synthetic rehearsal fixture. Production authority must stay unchanged.
package runtimeapi

import "testing"

func TestValidateAuthorizedSourceRefDevFixturePrefix(t *testing.T) {
	fixture := "r2://nexus/uiw/test-fixtures/live-proof-20260827-sample_backup.xml"

	t.Setenv("PLATFORM_DEV_AUTH_BYPASS", "")
	if _, _, err := validateAuthorizedSourceRef(fixture); err == nil {
		t.Fatal("dev fixture prefix must be rejected when PLATFORM_DEV_AUTH_BYPASS is unset")
	}

	t.Setenv("PLATFORM_DEV_AUTH_BYPASS", "1")
	scheme, key, err := validateAuthorizedSourceRef(fixture)
	if err != nil {
		t.Fatalf("dev fixture prefix must be accepted under the dev flag: %v", err)
	}
	if scheme != "r2" || key != "uiw/test-fixtures/live-proof-20260827-sample_backup.xml" {
		t.Fatalf("unexpected parse: scheme=%q key=%q", scheme, key)
	}

	// The flag never widens beyond the fixture prefix or the fixture bucket.
	for _, bad := range []string{
		"r2://nexus/other/file.xml",
		"r2://nexus/uiw/test-fixtures/../escape.xml",
		"r2://casebible-raw/anything.xml",
		"r2://photos/uiw/test-fixtures/x.xml",
	} {
		if _, _, err := validateAuthorizedSourceRef(bad); err == nil {
			t.Fatalf("%s must be rejected even under the dev flag", bad)
		}
	}

	// Canonical sources are unaffected by the flag in either state.
	for _, flag := range []string{"", "1"} {
		t.Setenv("PLATFORM_DEV_AUTH_BYPASS", flag)
		if _, _, err := validateAuthorizedSourceRef("r2://casebible-sorted/Messaging/x.html"); err != nil {
			t.Fatalf("casebible-sorted must always be accepted (flag=%q): %v", flag, err)
		}
	}
}
