// This file implements the narrow, production source-metadata extractors and
// member enumerator activities.SourceObservationActivities needs for a
// retained object. It stays strictly observational: it stats or looks up
// facts that already exist, never parses content, never hashes, and never
// invents a fact this process cannot directly observe. Because a single
// activities.SourceMetadataExtractor value serves both the filesystem and
// embedded metadata stages from an identical input (SourceObservationInput
// carries no stage marker), the two concerns are two separate extractor
// values here rather than one that tries to guess which stage called it; a
// caller wires each into its own stage-scoped activities.SourceObservationActivities.
package runtimeapi

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/google/uuid"
)

const (
	filesystemMetadataExtractorID      = "runtimeapi.filesystem_stat"
	filesystemMetadataExtractorVersion = "1.0.0"
)

// NewFilesystemMetadataExtractor resolves the retained object behind a source
// observation's original reference and reports its exact filesystem-native
// facts: the retained_object's own storage accounting (URI, byte length,
// content digest, retention timestamp) plus, when the object is
// filesystem-backed, the on-disk stat (size, modification time, mode). It
// never opens or reads the object's content.
func NewFilesystemMetadataExtractor(db platformpostgres.DB) (activities.SourceMetadataExtractor, error) {
	if db == nil {
		return nil, errors.New("filesystem metadata extractor: database is required")
	}
	return &filesystemMetadataExtractor{db: db, clock: func() time.Time { return time.Now().UTC() }}, nil
}

type filesystemMetadataExtractor struct {
	db    platformpostgres.DB
	clock func() time.Time
}

func (e *filesystemMetadataExtractor) ExtractSourceMetadata(ctx context.Context, input activities.SourceObservationInput) (activities.MetadataObservation, error) {
	if err := ctx.Err(); err != nil {
		return activities.MetadataObservation{}, err
	}
	object, provenanceClass, err := resolveRetainedObjectForObservation(ctx, e.db, input)
	if err != nil {
		return activities.MetadataObservation{}, err
	}
	fields := map[string]any{
		"object_uri":     object.objectURI,
		"storage_class":  object.storageClass,
		"byte_length":    object.byteLength,
		"content_sha256": hex.EncodeToString(object.contentSHA256),
		"immutable_at":   object.immutableAt.UTC().Format(time.RFC3339Nano),
	}
	if object.storageClass == "filesystem" {
		path, err := pathFromFileURI(object.objectURI)
		if err != nil {
			return activities.MetadataObservation{}, fmt.Errorf("resolve retained filesystem object path: %w", err)
		}
		info, err := os.Stat(path)
		if err != nil {
			return activities.MetadataObservation{}, fmt.Errorf("stat retained filesystem object: %w", err)
		}
		fields["name"] = info.Name()
		fields["size_bytes"] = info.Size()
		fields["modified_at"] = info.ModTime().UTC().Format(time.RFC3339Nano)
		fields["mode"] = info.Mode().String()
		fields["is_dir"] = info.IsDir()
	}
	payload, err := json.Marshal(fields)
	if err != nil {
		return activities.MetadataObservation{}, fmt.Errorf("encode filesystem metadata: %w", err)
	}
	return activities.MetadataObservation{
		ProvenanceClass: provenanceClass,
		Rows: []activities.MetadataRow{{
			MetadataClass:    activities.MetadataClassFilesystem,
			Metadata:         payload,
			ExtractorID:      filesystemMetadataExtractorID,
			ExtractorVersion: filesystemMetadataExtractorVersion,
			GeneratedAt:      e.now(),
		}},
	}, nil
}

func (e *filesystemMetadataExtractor) now() time.Time {
	if e.clock == nil {
		return time.Now().UTC()
	}
	return e.clock()
}

// NewEmbeddedMetadataExtractor durably reports that this runtime has no
// embedded/container/media-tool metadata reader wired in. It always returns a
// valid, empty MetadataObservation (a durable not-applicable result once
// persisted) rather than fabricating a native metadata payload it has no tool
// to actually produce. Swap this for a real exiftool/format-specific reader
// once one exists, without touching the filesystem extractor above.
func NewEmbeddedMetadataExtractor(db platformpostgres.DB) (activities.SourceMetadataExtractor, error) {
	if db == nil {
		return nil, errors.New("embedded metadata extractor: database is required")
	}
	return &embeddedMetadataExtractor{db: db}, nil
}

type embeddedMetadataExtractor struct {
	db platformpostgres.DB
}

func (e *embeddedMetadataExtractor) ExtractSourceMetadata(ctx context.Context, input activities.SourceObservationInput) (activities.MetadataObservation, error) {
	if err := ctx.Err(); err != nil {
		return activities.MetadataObservation{}, err
	}
	_, provenanceClass, err := resolveRetainedObjectForObservation(ctx, e.db, input)
	if err != nil {
		return activities.MetadataObservation{}, err
	}
	return activities.MetadataObservation{ProvenanceClass: provenanceClass}, nil
}

type retainedObservationObject struct {
	storageClass  string
	objectURI     string
	byteLength    int64
	contentSHA256 []byte
	immutableAt   time.Time
}

// resolveRetainedObjectForObservation resolves the exact retained original
// object and its owning source version in one query. Resolving the two compact
// references independently would permit metadata from one source to be
// persisted under another source's provenance, so the join requires the
// source to be retained and the object to be its original-role member.
// Both extractors share this boundary so their custody rule cannot drift.
func resolveRetainedObjectForObservation(ctx context.Context, db platformpostgres.DB, input activities.SourceObservationInput) (retainedObservationObject, string, error) {
	sourceVersionID, err := uuid.Parse(string(input.SourceVersionRef))
	if err != nil {
		return retainedObservationObject{}, "", fmt.Errorf("source observation source version reference %q is not a source version id: %w", input.SourceVersionRef, err)
	}
	objectID, err := uuid.Parse(string(input.OriginalRef))
	if err != nil {
		return retainedObservationObject{}, "", fmt.Errorf("source observation original reference %q is not a retained object id: %w", input.OriginalRef, err)
	}
	var object retainedObservationObject
	var provenanceClass string
	if err := db.QueryRow(ctx, `
		SELECT object.storage_class, object.object_uri, object.byte_length,
		       object.content_sha256, object.immutable_at, source.provenance_class
		FROM context.source_version version
		JOIN context.source source ON source.id = version.source_id
		JOIN context.retained_object object ON object.id = version.original_object_id
		JOIN context.source_version_object membership
		  ON membership.source_version_id = version.id
		 AND membership.object_id = object.id
		 AND membership.object_role = 'original'
		WHERE version.id = $1::uuid
		  AND object.id = $2::uuid
		  AND version.status = 'retained'`, sourceVersionID, objectID).Scan(
		&object.storageClass, &object.objectURI, &object.byteLength, &object.contentSHA256,
		&object.immutableAt, &provenanceClass); err != nil {
		return retainedObservationObject{}, "", fmt.Errorf("resolve retained original membership for source observation: %w", err)
	}
	return object, provenanceClass, nil
}

// NewNonContainerMemberEnumerator reports every retained object as
// structurally non-container: EnumerateMembers always returns
// activities.ErrNotApplicable rather than inventing a synthetic whole-object
// member. A real container walker (zip, mbox, pst, ...) is a distinct,
// format-specific capability this narrow implementation intentionally does
// not attempt; it covers only the "this source has no container member
// structure" determination every whole-object retained source needs.
func NewNonContainerMemberEnumerator() activities.MemberEnumerator {
	return nonContainerMemberEnumerator{}
}

type nonContainerMemberEnumerator struct{}

func (nonContainerMemberEnumerator) EnumerateMembers(_ context.Context, input activities.SourceObservationInput) (activities.MemberStream, error) {
	format := strings.TrimSpace(input.DeclaredFormat)
	if format == "" {
		format = "unknown"
	}
	return nil, fmt.Errorf("%w: declared format %q has no container member structure", activities.ErrNotApplicable, format)
}
