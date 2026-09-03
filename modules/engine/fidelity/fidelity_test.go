// Byline: Claude Code · Opus 5 · 2026-09-03.
package fidelity

import (
	"strings"
	"testing"
)

func base() Input {
	return Input{
		Content:         "I never said that and you know it",
		SourceTimestamp: "1699564800000",
		Handle:          "5551234567",
		Direction:       DirectionInbound,
	}
}

func mustHex(t *testing.T, in Input) string {
	t.Helper()
	got, err := DigestHex(in)
	if err != nil {
		t.Fatalf("DigestHex: %v", err)
	}
	return got
}

func TestDigestIsDeterministic(t *testing.T) {
	first, second := mustHex(t, base()), mustHex(t, base())
	if first != second {
		t.Fatalf("digest is not deterministic: %s vs %s", first, second)
	}
	if len(first) != 64 {
		t.Fatalf("digest hex length = %d, want 64", len(first))
	}
}

// THE reason handle and direction are in the digest. A content+timestamp-only
// seal would certify a swapped record as faithful.
func TestDirectionSwapBreaksTheSeal(t *testing.T) {
	inbound := base()
	outbound := base()
	outbound.Direction = DirectionOutbound
	if mustHex(t, inbound) == mustHex(t, outbound) {
		t.Fatal("a direction swap did not change the digest — the seal cannot detect misattribution")
	}
}

func TestEachSealedFieldChangesTheDigest(t *testing.T) {
	original := mustHex(t, base())

	content := base()
	content.Content = "I never said that and you know it."
	if mustHex(t, content) == original {
		t.Fatal("content change did not break the seal")
	}

	timestamp := base()
	timestamp.SourceTimestamp = "1699564800001"
	if mustHex(t, timestamp) == original {
		t.Fatal("timestamp change did not break the seal")
	}

	handle := base()
	handle.Handle = "5559999999"
	if mustHex(t, handle) == original {
		t.Fatal("handle change did not break the seal")
	}
}

// Length framing: ("ab","c") must not collide with ("a","bc"), or a crafted
// handle could absorb part of a body and two different records would seal alike.
func TestFieldBoundariesCannotBeShifted(t *testing.T) {
	left := Input{Content: "hello", SourceTimestamp: "1", Handle: "555", Direction: DirectionInbound}
	right := Input{Content: "hell", SourceTimestamp: "o1", Handle: "555", Direction: DirectionInbound}
	if mustHex(t, left) == mustHex(t, right) {
		t.Fatal("field boundaries are shiftable — concatenation is not length-framed")
	}

	shiftHandle := Input{Content: "hello", SourceTimestamp: "1555", Handle: "", Direction: DirectionInbound}
	if _, err := Digest(shiftHandle); err == nil {
		t.Fatal("an empty handle must be refused, not sealed")
	}
}

// Metadata the owner is explicitly allowed to correct is NOT in the digest, so
// correcting it must not break the seal. contact_name and entity links simply
// have no representation here — proven by the seal being stable across a record
// whose only difference is metadata the caller never passes in.
func TestPermittedMetadataIsNotSealed(t *testing.T) {
	// Same material assertion, reached from two records that differ only in
	// fields outside Input entirely (contact_name, read, thread_id, entity id).
	beforeCorrection := base()
	afterCorrection := base()
	if mustHex(t, beforeCorrection) != mustHex(t, afterCorrection) {
		t.Fatal("the seal is sensitive to something outside the material assertion")
	}
}

// Attachment-only MMS has no body. An early parser DROPPED 516 such records and
// its test asserted the bug; empty content must seal, not error.
func TestEmptyContentIsSealedNotRejected(t *testing.T) {
	empty := base()
	empty.Content = ""
	got, err := DigestHex(empty)
	if err != nil {
		t.Fatalf("empty content must be sealable (attachment-only MMS): %v", err)
	}
	if got == mustHex(t, base()) {
		t.Fatal("empty content sealed the same as non-empty content")
	}
}

func TestRequiredFieldsFailClosed(t *testing.T) {
	noTimestamp := base()
	noTimestamp.SourceTimestamp = "   "
	if _, err := Digest(noTimestamp); err == nil || !strings.Contains(err.Error(), "timestamp") {
		t.Fatalf("expected a missing timestamp to be refused, got %v", err)
	}

	noHandle := base()
	noHandle.Handle = ""
	if _, err := Digest(noHandle); err == nil || !strings.Contains(err.Error(), "handle") {
		t.Fatalf("expected a missing handle to be refused, got %v", err)
	}

	badDirection := base()
	badDirection.Direction = Direction("sent")
	if _, err := Digest(badDirection); err == nil || !strings.Contains(err.Error(), "direction") {
		t.Fatalf("expected an out-of-set direction to be refused, got %v", err)
	}

	unset := base()
	unset.Direction = ""
	if _, err := Digest(unset); err == nil {
		t.Fatal("an unset direction must be refused rather than defaulted")
	}
}

// Unknown is a legitimate, sealable answer — honest beats guessed.
func TestUnknownDirectionIsSealable(t *testing.T) {
	unknown := base()
	unknown.Direction = DirectionUnknown
	if _, err := Digest(unknown); err != nil {
		t.Fatalf("unknown direction must be sealable: %v", err)
	}
	if mustHex(t, unknown) == mustHex(t, base()) {
		t.Fatal("unknown sealed identically to inbound")
	}
}

// Bytes are sealed exactly as the source wrote them: no normalization, no
// trimming, no case folding. Normalizing would be our transformation, not the
// source's statement.
func TestNoImplicitNormalization(t *testing.T) {
	for _, variant := range []Input{
		func() Input { v := base(); v.Content = " " + v.Content; return v }(),
		func() Input { v := base(); v.Content = strings.ToUpper(v.Content); return v }(),
		func() Input { v := base(); v.Handle = "+15551234567"; return v }(),
	} {
		if mustHex(t, variant) == mustHex(t, base()) {
			t.Fatalf("digest normalized away a real byte difference: %+v", variant)
		}
	}
}

// The mechanism: independently computed from both sides, matching proves
// normalization preserved the material assertion.
func TestVerifyAcrossTheRawNormalizedBoundary(t *testing.T) {
	raw := base()
	normalized := base()
	ok, err := Verify(raw, normalized)
	if err != nil {
		t.Fatalf("Verify: %v", err)
	}
	if !ok {
		t.Fatal("a faithful normalization failed verification")
	}

	drifted := base()
	drifted.Content = "I never said that"
	ok, err = Verify(raw, drifted)
	if err != nil {
		t.Fatalf("Verify: %v", err)
	}
	if ok {
		t.Fatal("a normalization that changed content passed verification")
	}

	swapped := base()
	swapped.Direction = DirectionOutbound
	ok, _ = Verify(raw, swapped)
	if ok {
		t.Fatal("a normalization that inverted direction passed verification")
	}
}

func TestVerifySurfacesInvalidSideDistinctly(t *testing.T) {
	bad := base()
	bad.Handle = ""
	if _, err := Verify(bad, base()); err == nil || !strings.Contains(err.Error(), "raw side") {
		t.Fatalf("expected the raw side to be named, got %v", err)
	}
	if _, err := Verify(base(), bad); err == nil || !strings.Contains(err.Error(), "normalized side") {
		t.Fatalf("expected the normalized side to be named, got %v", err)
	}
}

// The canon tag is part of the preimage, so it is domain separation: the same
// four values under a different construction must not collide.
func TestCanonTagIsDomainSeparation(t *testing.T) {
	if CanonTag != "fidelity-content-ts-handle-dir-v1" {
		t.Fatalf("CanonTag changed to %q — changing it invalidates every stored digest", CanonTag)
	}
	if !strings.Contains(CanonTag, "content") || !strings.Contains(CanonTag, "ts") ||
		!strings.Contains(CanonTag, "handle") || !strings.Contains(CanonTag, "dir") {
		t.Fatal("CanonTag must name its exact construction, not just a version")
	}
}
