// Package fidelity computes the FIDELITY DIGEST — the narrow seal that proves a
// normalized message record still says what its source said.
//
// WHY THIS IS NOT H2 (owner ruling D-136, design 2026-09-02/03)
//
// H2 already hashes the ENTIRE raw record element. That is correct for custody
// of the source, but it is the wrong seal for the working record, because H2
// breaks the moment ANY field changes — including the fields the owner is
// explicitly permitted to change:
//
//	D-136: "Ensure that every last bit of data is extracted. Don't modify the
//	messages and the timestamps. Let me do what the fuck else I want."
//
// Correcting a `contact_name`, linking a handle to a Person entity, fixing a
// thread label — all permitted, and all of them break H2. So a seal that only
// covers the MATERIAL assertion is what makes that permission safe: metadata
// stays free precisely because it is outside the digest, and content stays
// immutable because it is inside it.
//
// WHAT IS SEALED, AND WHY EACH FIELD IS THERE
//
//	content    — what was said. Obviously material.
//	timestamp  — when. Obviously material.
//	handle     — the participant identifier AS THE SOURCE RECORDED IT.
//	direction  — who spoke.
//
// The last two are not padding. Content+timestamp alone CANNOT DETECT A
// DIRECTION SWAP: if normalization ever flipped sender and recipient, a
// content+timestamp digest would still match and certify the record as
// faithful while the meaning inverted — her words attributed to him. In a
// coercive-control matter that is the worst failure this system could produce.
// Short messages also collide constantly ("ok", "?", "yes") without a
// participant in the digest.
//
// WHAT IS DELIBERATELY EXCLUDED
//
//	contact_name  — the device's local address-book label, not a fact about the
//	                message. It is a weak resolution signal ("basis: device
//	                address book"), and correcting it must never break a seal.
//	read/thread   — device state, not what was said.
//	entity UUIDs  — resolution is a revisable judgment; putting it in the
//	                digest would break the seal on a permitted correction.
//	derived clocks— source_available_from / knowledge_time are OURS, not the
//	                sender's (ADR-0059).
//
// # CANONICALIZATION IS THE WHOLE GAME
//
// A digest is worthless if the same logical record can hash two ways. Two live
// hazards were found in the as-built schema and both are handled here rather
// than at the call site:
//
//   - `occurred_at` is TIMESTAMPTZ, which PostgreSQL renders in the SESSION
//     timezone. Hashing a rendered value means a client in another timezone
//     produces a different digest for identical data. So this package takes the
//     SOURCE'S OWN timestamp string, verbatim, and never a database rendering.
//   - `participants` is JSONB, whose byte serialization is not stable across
//     writes or versions. So this package takes a single already-extracted
//     handle string, never a JSON blob.
//
// Bytes are hashed exactly as the source wrote them. No Unicode normalization,
// no trimming, no case folding: normalizing would be a transformation, and the
// point is to seal what the source actually said.
//
// Byline: Claude Code · Opus 5 · 2026-09-03.
package fidelity

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// CanonTag names the EXACT construction, not merely a version. Platform rule:
// a hash tag that does not identify its construction is a defect — two
// different-but-valid constructions once shared the tag `h3-chain-v1` and
// could not be told apart afterwards.
//
// Construction identified by this tag:
//
//	domain    = "fidelity-content-ts-handle-dir-v1"
//	preimage  = frame(domain) || frame(content) || frame(timestamp) ||
//	            frame(handle) || frame(direction)
//	frame(s)  = uint64_be(len(s)) || s        (length-framed, no separators)
//	digest    = SHA-256(preimage)
//
// Length framing is required: plain concatenation would let ("ab","c") and
// ("a","bc") collide, which would let a crafted handle absorb part of a body.
const CanonTag = "fidelity-content-ts-handle-dir-v1"

// Direction is who spoke, normalized to a closed set.
//
// Direction is the one sealed field that is DERIVED rather than copied, because
// every source encodes it differently (SMS `type=1|2`, iMessage `is_from_me`,
// Facebook by comparing sender_name to the account owner). It is sealed anyway,
// and that is the point: once parsed, a later flip breaks the digest.
//
// Note the standing hazard this cannot fix by itself: SMS/iMessage direction is
// DEVICE-RELATIVE. "Sent" means sent by whoever owned that device, so direction
// is only meaningful against a declared perspective on the source version. Get
// the perspective wrong at parse time and the digest faithfully seals a wrong
// answer.
type Direction string

const (
	// DirectionOutbound: authored by the custodian of this source version.
	DirectionOutbound Direction = "outbound"
	// DirectionInbound: authored by the other party.
	DirectionInbound Direction = "inbound"
	// DirectionUnknown: the source does not state it and it cannot be
	// derived. Recorded honestly rather than guessed — a guessed direction
	// sealed into a digest is a fabricated fact wearing a certificate.
	DirectionUnknown Direction = "unknown"
)

func (d Direction) valid() bool {
	switch d {
	case DirectionOutbound, DirectionInbound, DirectionUnknown:
		return true
	}
	return false
}

// Input is the material assertion of one message record.
//
// Every field is taken VERBATIM from the source except Direction, which is
// derived once at parse time. Callers must not pre-normalize any of them.
type Input struct {
	// Content is the message body exactly as the source recorded it.
	Content string

	// SourceTimestamp is the source's OWN timestamp string, verbatim — the
	// `date`/`readable_date` attribute, the `<abbr class="dt" title=...>`
	// value, whatever the export wrote. NOT a database rendering and NOT a
	// reformatted time, because reformatting is our transformation, not the
	// source's statement.
	SourceTimestamp string

	// Handle is the participant identifier as the source recorded it: a phone
	// number, a Facebook id, an email. NEVER contact_name, and never a
	// resolved entity UUID.
	Handle string

	// Direction is who spoke, relative to the declared perspective on this
	// source version.
	Direction Direction
}

func (in Input) validate() error {
	// Content may legitimately be empty — an attachment-only MMS has no body,
	// and an early parser once DROPPED 516 such records while its test
	// asserted the bug. Empty content is sealed as empty, never rejected.
	if strings.TrimSpace(in.SourceTimestamp) == "" {
		return errors.New("fidelity: source timestamp is required and must be the source's own value")
	}
	if strings.TrimSpace(in.Handle) == "" {
		return errors.New("fidelity: handle is required (the source's own identifier, never contact_name)")
	}
	if !in.Direction.valid() {
		return fmt.Errorf("fidelity: direction %q is not one of outbound/inbound/unknown", in.Direction)
	}
	return nil
}

// Digest computes the fidelity digest over the material assertion.
//
// The same function MUST be used on both sides of the raw↔normalized boundary.
// That is the entire mechanism: a digest computed independently from the raw
// record and from the normalized record, matching, is proof that normalization
// preserved what the source said. Computing it only once, or computing it from
// the normalized side alone, proves nothing.
func Digest(in Input) ([32]byte, error) {
	var zero [32]byte
	if err := in.validate(); err != nil {
		return zero, err
	}
	hasher := sha256.New()
	for _, field := range []string{
		CanonTag,
		in.Content,
		in.SourceTimestamp,
		in.Handle,
		string(in.Direction),
	} {
		var length [8]byte
		binary.BigEndian.PutUint64(length[:], uint64(len(field)))
		hasher.Write(length[:])
		hasher.Write([]byte(field))
	}
	var out [32]byte
	copy(out[:], hasher.Sum(nil))
	return out, nil
}

// DigestHex is Digest as lowercase hex, the form stored and compared.
func DigestHex(in Input) (string, error) {
	sum, err := Digest(in)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(sum[:]), nil
}

// Verify reports whether a raw-side and normalized-side input seal identically.
//
// A false result means normalization changed the material assertion — content,
// timestamp, participant, or direction. That is a fail-closed condition at
// promotion: it must block, never warn.
func Verify(raw, normalized Input) (bool, error) {
	rawSum, err := Digest(raw)
	if err != nil {
		return false, fmt.Errorf("fidelity: raw side: %w", err)
	}
	normSum, err := Digest(normalized)
	if err != nil {
		return false, fmt.Errorf("fidelity: normalized side: %w", err)
	}
	// Digests are public integrity values, not secrets; a plain comparison is
	// appropriate and there is no timing channel worth defending here.
	return rawSum == normSum, nil
}
