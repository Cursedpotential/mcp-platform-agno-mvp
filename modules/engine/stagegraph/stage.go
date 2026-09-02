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

// ChunkDocument is the canon Activity name for the skip-to-chunk capability
// (D-116 / owner ruling 2026-08-29: "if it doesn't need to be parsed and
// really needs to be chunked and ingested, so be it"). It runs when a route
// decision says chunk-not-parse rather than execute_parser_activity.
//
// ChunkDocument is deliberately NOT a member of Stages. Stages is the
// exhaustive, fully-convergent DAG behind UniversalImportWorkflow's 26 canon
// stages: graph_test.go's requiredStages map fails closed on any stage not
// in that exact set (TestEveryRequiredStageAppearsExactlyOnce), and
// TestPublishRequiresAllGates/TestNoStageReachesPublishWithoutItsOwnGate
// together prove every single entry in Stages is a transitive ancestor of
// PublishGeneration — the graph has no vocabulary for an alternate,
// mutually-exclusive path (chunk-not-parse is an OR-branch against
// ExecuteParser, not a converging AND-dependency). Splicing ChunkDocument
// into Stages today would either violate that invariant or force every
// existing stage's DependsOn to route around it, which is a real workflow
// restructuring, not a stage addition — see the wiring-plan note in
// engine/activities/chunking.go and the BUILD LANE C1 handoff for the exact
// steps that restructuring needs (a workflow.GetVersion-gated branch, plus a
// graph invariant that can express alternation).
//
// The Activity is fully real and Temporal-callable today: it is registered
// on the UIW worker (uiwworker.RegisterAll) exactly like every Stages
// member, using the same uiw.StageRequest/uiw.StageResult wire contract, so
// a future gated branch in UniversalImportWorkflow can call it via the
// existing r.exec helper with no signature change. It is simply not yet
// invoked by the workflow.
const ChunkDocument StageID = "chunk_document_activity"
