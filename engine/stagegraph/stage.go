// Package stagegraph locks the atomic stage graph of the future Temporal
// UniversalImportWorkflow described in
// docs/reviews/2026-08-25-schema-audit/SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html.
//
// It has no Temporal dependency. It exists so the exact stage set, their
// single-responsibility boundaries, and their dependency edges can be
// reviewed and tested before any Temporal SDK code is written.
package stagegraph

// StageID names one atomic Activity in the UniversalImportWorkflow, matching
// the canon activity names in the boundary document section 2.
type StageID string

const (
	RegisterSource                 StageID = "register_source_activity"
	RetainOriginal                 StageID = "retain_original_activity"
	AssessSourceRepair             StageID = "assess_source_repair_activity"
	ResolveSourceRepair            StageID = "resolve_source_repair_activity"
	CaptureFilesystemMetadata      StageID = "capture_filesystem_metadata_activity"
	FingerprintSource              StageID = "fingerprint_source_activity"
	InventoryContainer             StageID = "inventory_container_activity"
	ExtractEmbeddedMetadata        StageID = "extract_embedded_metadata_activity"
	SelectParser                   StageID = "select_parser_activity"
	ExecuteParser                  StageID = "execute_parser_activity"
	PersistRawGeneration           StageID = "persist_raw_generation_activity"
	FingerprintRawRecords          StageID = "fingerprint_raw_records_activity"
	FingerprintRawGeneration       StageID = "fingerprint_raw_generation_activity"
	ReconcileRecordAccounting      StageID = "reconcile_record_accounting_activity"
	ReconcileByteCoverage          StageID = "reconcile_byte_coverage_activity"
	VerifyRawCoverageAgainstSource StageID = "verify_raw_coverage_against_source_activity"
	NormalizeGeneration            StageID = "normalize_generation_activity"
	PersistNormalizedGeneration    StageID = "persist_normalized_generation_activity"
	PersistLineage                 StageID = "persist_lineage_activity"
	ValidateRawLineage             StageID = "validate_raw_lineage_activity"
	HashNormalizedRecords          StageID = "hash_normalized_records_activity"
	HashNormalizedGeneration       StageID = "hash_normalized_generation_activity"
	VerifyNormalizedGeneration     StageID = "verify_normalized_generation_activity"
	PublishPreview                 StageID = "publish_preview_activity"
	SealGeneration                 StageID = "seal_generation_activity"
	PublishGeneration              StageID = "publish_generation_activity"
)

// Responsibility is a single-bit tag naming the one atomic side-effect a
// stage owns. A Descriptor must carry exactly one bit: the boundary document
// requires "one atomic responsibility, one side-effect boundary" per Activity.
type Responsibility uint32

const (
	RespRegisterIdentity Responsibility = 1 << iota
	RespRetain
	RespCaptureMetadata
	RespComputeHash
	RespInventory
	RespExtractMetadata
	RespSelect
	RespParse
	RespPersist
	RespReconcile
	RespVerify
	RespNormalize
	RespValidate
	RespSeal
	RespPublish
	RespAssessRepair
	RespResolveRepair
	RespProjectPreview
)

// Descriptor is the static, dependency-free description of one stage: its
// single responsibility, the compact result it hands downstream, and which
// other stages must complete before it may start.
type Descriptor struct {
	ID             StageID
	Responsibility Responsibility
	Result         string
	DependsOn      []StageID
}
