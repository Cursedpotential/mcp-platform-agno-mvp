package stagegraph

// Stages is the ordered, exhaustive registry of every Activity in the
// UniversalImportWorkflow. Order follows the canon document's numbering
// (section 2) purely for readability; the actual execution order is
// determined by DependsOn, not slice position.
//
// Hash-naming discipline (vendored/sbv/CUSTODY.md is authoritative): H1 is
// the whole-source digest, H2 is the per-raw-record/span digest, and H3 is
// the order-sensitive fold of the ordered H2 digests — a raw-custody
// concept, never a comparison to normalized output. The platform raw-all
// H3 uses the tested SBV fold implementation under its own membership tag
// because envelope/unparsed spans are also members. hash_normalized_records
// and hash_normalized_generation compute separately-named
// normalized-record digests and a normalized-generation manifest digest;
// neither is H2 nor H3, and reconciliation/verification of one hash against
// another remains a distinct responsibility from computing it.
//
// Dependency rationale, mirroring the canon document:
//
//   - register_source is the root: it creates the identity/idempotency
//     coordinate every other stage keys off.
//   - retain_original is the only stage after register_source that must run
//     before anything touches source bytes.
//   - capture_filesystem_metadata, hash_source (H1), inventory_container, and
//     extract_embedded_metadata are the named "safe parallel fan-out": each
//     depends only on retain_original and not on one another.
//   - select_parser joins that fan-out (it needs the container manifest and
//     metadata manifest to pick an adapter) before execute_parser runs.
//   - persist_raw_generation, hash_raw_records (H2 per raw record/span), then
//     hash_raw_generation (H3, the ordered H2 chain) follow parsing in strict
//     sequence (persist before hashing the persisted rows, hash the members
//     before folding their chain).
//   - reconcile_record_accounting and reconcile_byte_coverage both depend
//     only on hash_raw_generation and not on each other (second parallel
//     pair) — reconciliation runs only once the raw generation's full custody
//     chain (H2 membership + H3 fold) has been computed.
//   - verify_raw_coverage_against_source joins that pair and additionally
//     depends on hash_source, since it compares raw coverage against H1.
//   - normalize_generation, persist_normalized_generation follow verification
//     in strict sequence (normalize is transform-only, persist is the only
//     write).
//   - persist_lineage -> validate_raw_lineage is one branch off
//     persist_normalized_generation; hash_normalized_records (normalized
//     record digests) is the other, independent branch (third parallel
//     pair).
//   - hash_normalized_generation (normalized generation manifest digest)
//     depends on hash_normalized_records, since it folds the ordered
//     normalized-record membership.
//   - verify_normalized_generation joins the lineage branch and the
//     normalized-digest branch before seal_generation may run.
//   - publish_generation is the sole successor of seal_generation, and is
//     therefore the sink whose transitive dependency closure is every other
//     stage.
var Stages = []Descriptor{
	{
		ID:             RegisterSource,
		Responsibility: RespRegisterIdentity,
		Result:         "source/version reference",
	},
	{
		ID:             RetainOriginal,
		Responsibility: RespRetain,
		Result:         "original-object reference",
		DependsOn:      []StageID{RegisterSource},
	},
	{
		ID:             CaptureFilesystemMetadata,
		Responsibility: RespCaptureMetadata,
		Result:         "filesystem metadata reference",
		DependsOn:      []StageID{RetainOriginal},
	},
	{
		ID:             FingerprintSource,
		Responsibility: RespComputeHash,
		Result:         "context source fingerprint receipt reference",
		DependsOn:      []StageID{RetainOriginal},
	},
	{
		ID:             InventoryContainer,
		Responsibility: RespInventory,
		Result:         "container manifest reference",
		DependsOn:      []StageID{RetainOriginal},
	},
	{
		ID:             ExtractEmbeddedMetadata,
		Responsibility: RespExtractMetadata,
		Result:         "metadata manifest reference",
		DependsOn:      []StageID{RetainOriginal},
	},
	{
		ID:             SelectParser,
		Responsibility: RespSelect,
		Result:         "parser selection receipt",
		DependsOn: []StageID{
			CaptureFilesystemMetadata,
			FingerprintSource,
			InventoryContainer,
			ExtractEmbeddedMetadata,
		},
	},
	{
		ID:             ExecuteParser,
		Responsibility: RespParse,
		Result:         "immutable bundle reference",
		DependsOn:      []StageID{SelectParser},
	},
	{
		ID:             PersistRawGeneration,
		Responsibility: RespPersist,
		Result:         "raw generation receipt",
		DependsOn:      []StageID{ExecuteParser},
	},
	{
		ID:             FingerprintRawRecords,
		Responsibility: RespComputeHash,
		Result:         "context raw-record fingerprint manifest reference",
		DependsOn:      []StageID{PersistRawGeneration},
	},
	{
		ID:             FingerprintRawGeneration,
		Responsibility: RespComputeHash,
		Result:         "context raw-generation fingerprint chain reference",
		DependsOn:      []StageID{FingerprintRawRecords},
	},
	{
		ID:             ReconcileRecordAccounting,
		Responsibility: RespReconcile,
		Result:         "accounting receipt",
		DependsOn:      []StageID{FingerprintRawGeneration},
	},
	{
		ID:             ReconcileByteCoverage,
		Responsibility: RespReconcile,
		Result:         "coverage receipt",
		DependsOn:      []StageID{FingerprintRawGeneration},
	},
	{
		ID:             VerifyRawCoverageAgainstSource,
		Responsibility: RespVerify,
		Result:         "raw/source verification receipt",
		DependsOn: []StageID{
			ReconcileRecordAccounting,
			ReconcileByteCoverage,
			FingerprintSource,
		},
	},
	{
		ID:             NormalizeGeneration,
		Responsibility: RespNormalize,
		Result:         "normalized bundle reference",
		DependsOn:      []StageID{VerifyRawCoverageAgainstSource},
	},
	{
		ID:             PersistNormalizedGeneration,
		Responsibility: RespPersist,
		Result:         "normalized generation reference",
		DependsOn:      []StageID{NormalizeGeneration},
	},
	{
		ID:             PersistLineage,
		Responsibility: RespPersist,
		Result:         "lineage-set reference",
		DependsOn:      []StageID{PersistNormalizedGeneration},
	},
	{
		ID:             ValidateRawLineage,
		Responsibility: RespValidate,
		Result:         "lineage validation receipt",
		DependsOn:      []StageID{PersistLineage},
	},
	{
		ID:             HashNormalizedRecords,
		Responsibility: RespComputeHash,
		Result:         "normalized record digest manifest reference",
		DependsOn:      []StageID{PersistNormalizedGeneration},
	},
	{
		ID:             HashNormalizedGeneration,
		Responsibility: RespComputeHash,
		Result:         "normalized generation manifest digest reference",
		DependsOn:      []StageID{HashNormalizedRecords},
	},
	{
		ID:             VerifyNormalizedGeneration,
		Responsibility: RespVerify,
		Result:         "normalized verification receipt",
		DependsOn: []StageID{
			ValidateRawLineage,
			HashNormalizedGeneration,
		},
	},
	{
		ID:             SealGeneration,
		Responsibility: RespSeal,
		Result:         "sealed generation receipt",
		DependsOn:      []StageID{VerifyNormalizedGeneration},
	},
	{
		ID:             PublishGeneration,
		Responsibility: RespPublish,
		Result:         "publication receipt",
		DependsOn:      []StageID{SealGeneration},
	},
}
