package postgres

import (
	"path/filepath"
	"testing"
)

func TestRepairStoreRejectsPathsOutsideSharedRoots(t *testing.T) {
	root := t.TempDir()
	store, err := NewRepairActivityStore(&artifactRegistrationDB{}, []string{root})
	if err != nil {
		t.Fatal(err)
	}
	if !store.pathAllowed(filepath.Join(root, "source.xml")) {
		t.Fatal("shared-root child was rejected")
	}
	if store.pathAllowed(filepath.Join(filepath.Dir(root), "outside.xml")) {
		t.Fatal("path outside shared root was accepted")
	}
}

func TestFileURIPathRejectsNetworkAndNonFileLocators(t *testing.T) {
	for _, raw := range []string{"https://example.invalid/a", "file://remote/share/a", "relative.xml"} {
		if _, err := fileURIPath(raw); err == nil {
			t.Fatalf("fileURIPath(%q) accepted", raw)
		}
	}
}
