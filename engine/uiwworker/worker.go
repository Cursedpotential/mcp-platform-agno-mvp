package uiwworker

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/activities"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/normalize"
	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/runtimeapi"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	platformtemporal "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/temporal"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Registrations contains the bounded Activity groups that collectively
// implement all 26 UIW stages. Filesystem and embedded observation bodies are
// separate values so extractor provenance cannot cross activity boundaries.
type Registrations struct {
	Lifecycle             activities.SourceLifecycleActivities
	FilesystemObservation activities.SourceObservationActivities
	InventoryObservation  activities.SourceObservationActivities
	EmbeddedObservation   activities.SourceObservationActivities
	N8N                   platformtemporal.N8NActivities
	Hash                  activities.HashActivities
	Raw                   activities.RawPipelineActivities
	Normalized            activities.NormalizedPipelineActivities
	Repair                activities.RepairActivities
	Preview               activities.PreviewProjectionActivity
}

// RegisterAll installs the one workflow plus every exact stagegraph name on
// one worker. A partial worker must never poll this task queue.
func RegisterAll(registrar interface {
	activities.ActivityRegistrar
	RegisterWorkflow(interface{})
}, registrations Registrations) {
	registrar.RegisterWorkflow(uiw.UniversalImportWorkflow)
	activities.RegisterSourceLifecycleActivities(registrar, registrations.Lifecycle)
	activities.RegisterFilesystemMetadataActivity(registrar, registrations.FilesystemObservation)
	activities.RegisterHashActivities(registrar, registrations.Hash)
	activities.RegisterInventoryContainerActivity(registrar, registrations.InventoryObservation)
	activities.RegisterEmbeddedMetadataActivity(registrar, registrations.EmbeddedObservation)
	registrar.RegisterActivityWithOptions(registrations.N8N.SelectParser, activity.RegisterOptions{Name: string(stagegraph.SelectParser)})
	registrar.RegisterActivityWithOptions(registrations.N8N.ExecuteParser, activity.RegisterOptions{Name: string(stagegraph.ExecuteParser)})
	activities.RegisterRawPipelineActivities(registrar, registrations.Raw)
	activities.RegisterNormalizedPipelineActivities(registrar, registrations.Normalized)
	activities.RegisterRepairActivities(registrar, registrations.Repair)
	activities.RegisterPreviewProjectionActivity(registrar, registrations.Preview)
}

// Run constructs concrete production adapters, verifies PostgreSQL and shared
// storage before polling, and serves the dedicated UIW queue until shutdown.
func Run(ctx context.Context, cfg Config) error {
	if stringsTrim(cfg.TemporalTaskQueue) == "" {
		return errors.New("uiw worker: TEMPORAL_TASK_QUEUE is required")
	}
	if cfg.TemporalTaskQueue == legacyEvidenceTaskQueue {
		return errors.New("uiw worker: refusing legacy evidence-pipeline task queue")
	}
	if err := validateSharedPaths(cfg); err != nil {
		return err
	}
	if err := prepareSharedPaths(cfg); err != nil {
		return err
	}

	pool, err := pgxpool.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return errors.New("uiw worker: configure platform database pool: invalid configuration")
	}
	defer pool.Close()
	if err := pool.Ping(ctx); err != nil {
		return errors.New("uiw worker: connect to platform database: unavailable")
	}
	if err := ProbeSchema(ctx, pool); err != nil {
		return err
	}

	registrations, err := buildRegistrations(pool, cfg)
	if err != nil {
		return err
	}
	temporalClient, err := client.Dial(client.Options{HostPort: cfg.TemporalHostPort, Namespace: cfg.TemporalNamespace})
	if err != nil {
		return fmt.Errorf("uiw worker: connect to Temporal: %w", err)
	}
	defer temporalClient.Close()

	temporalWorker := worker.New(temporalClient, cfg.TemporalTaskQueue, worker.Options{})
	RegisterAll(temporalWorker, registrations)
	if err := temporalWorker.Start(); err != nil {
		return fmt.Errorf("uiw worker: start Temporal worker: %w", err)
	}
	slog.Info("universal import worker started", "task_queue", cfg.TemporalTaskQueue, "namespace", cfg.TemporalNamespace, "activity_count", len(stagegraph.Stages))
	<-ctx.Done()
	temporalWorker.Stop()
	return nil
}

func buildRegistrations(pool *pgxpool.Pool, cfg Config) (Registrations, error) {
	openObject, err := runtimeapi.NewRetainedObjectOpener(pool)
	if err != nil {
		return Registrations{}, err
	}
	acquisitionResolver, err := runtimeapi.NewFilesystemImmutableAcquisitionResolver(cfg.SourceObjectDir)
	if err != nil {
		return Registrations{}, err
	}
	lifecycleRepo, err := platformpostgres.NewSourceLifecycleRepository(pool, acquisitionResolver)
	if err != nil {
		return Registrations{}, err
	}
	manifestFactory, err := runtimeapi.NewFilesystemInventoryManifestFactory(cfg.InventoryManifestDir)
	if err != nil {
		return Registrations{}, err
	}
	observationRepo, err := platformpostgres.NewSourceObservationRepository(pool, manifestFactory)
	if err != nil {
		return Registrations{}, err
	}
	filesystemExtractor, err := runtimeapi.NewFilesystemMetadataExtractor(pool)
	if err != nil {
		return Registrations{}, err
	}
	embeddedExtractor, err := runtimeapi.NewEmbeddedMetadataExtractor(pool)
	if err != nil {
		return Registrations{}, err
	}
	hashRepo, err := platformpostgres.NewRepository(pool, openObject)
	if err != nil {
		return Registrations{}, err
	}
	rawRepo, err := platformpostgres.NewRawPipelineRepository(pool, openObject)
	if err != nil {
		return Registrations{}, err
	}
	normalizedWriter, err := runtimeapi.NewFilesystemNormalizedBundleFactory(pool, cfg.NormalizedBundleDir)
	if err != nil {
		return Registrations{}, err
	}
	normalizedReader, err := runtimeapi.NewFilesystemNormalizedBundleReaderFactory(pool, openObject)
	if err != nil {
		return Registrations{}, err
	}
	normalizedRepo, err := platformpostgres.NewNormalizedPipelineRepository(pool, normalizedWriter, normalizedReader)
	if err != nil {
		return Registrations{}, err
	}
	repairStore, err := platformpostgres.NewRepairActivityStore(pool, []string{cfg.SourceObjectDir, cfg.ParserBundleDir, cfg.NormalizedBundleDir})
	if err != nil {
		return Registrations{}, err
	}
	toolsClient, err := runtimeapi.NewPlatformToolsClient(cfg.PlatformToolsBaseURL)
	if err != nil {
		return Registrations{}, err
	}
	previewStore, err := platformpostgres.NewUIWPreviewStore(pool, nil)
	if err != nil {
		return Registrations{}, err
	}
	n8nClient, err := platformtemporal.NewN8NClient(cfg.temporalConfig())
	if err != nil {
		return Registrations{}, err
	}
	return Registrations{
		Lifecycle:             activities.NewSourceLifecycleActivities(lifecycleRepo),
		FilesystemObservation: activities.NewSourceObservationActivities(filesystemExtractor, nil, observationRepo),
		InventoryObservation:  activities.NewSourceObservationActivities(nil, runtimeapi.NewNonContainerMemberEnumerator(), observationRepo),
		EmbeddedObservation:   activities.NewSourceObservationActivities(embeddedExtractor, nil, observationRepo),
		N8N:                   platformtemporal.N8NActivities{Client: n8nClient},
		Hash:                  activities.NewHashActivities(hashRepo),
		Raw:                   activities.NewRawPipelineActivities(rawRepo),
		Normalized:            activities.NewNormalizedPipelineActivities(normalizedRepo, normalize.GenericMessageNormalizer{}),
		Repair:                activities.NewRepairActivities(toolsClient, repairStore),
		Preview:               activities.PreviewProjectionActivity{Store: previewStore},
	}, nil
}

func prepareSharedPaths(cfg Config) error {
	for name, path := range map[string]string{
		"SOURCE_OBJECT_DIR":      cfg.SourceObjectDir,
		"PARSER_BUNDLE_DIR":      cfg.ParserBundleDir,
		"NORMALIZED_BUNDLE_DIR":  cfg.NormalizedBundleDir,
		"INVENTORY_MANIFEST_DIR": cfg.InventoryManifestDir,
	} {
		if err := os.MkdirAll(path, 0o750); err != nil {
			return fmt.Errorf("uiw worker: create %s: %w", name, err)
		}
		info, err := os.Lstat(path)
		if err != nil {
			return fmt.Errorf("uiw worker: inspect %s: %w", name, err)
		}
		if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("uiw worker: %s must be a real directory", name)
		}
		resolved, err := filepath.EvalSymlinks(path)
		if err != nil || filepath.Clean(resolved) != filepath.Clean(path) {
			return fmt.Errorf("uiw worker: %s must not traverse a symlink or junction", name)
		}
	}
	return nil
}

func stringsTrim(value string) string {
	return strings.TrimSpace(value)
}

// ProbeSchema is the startup admission gate. It verifies the fresh platform
// database, active migration ledger, all required context tables, runtime role
// membership, and absence of elevated role attributes before the queue is
// polled.
func ProbeSchema(ctx context.Context, pool *pgxpool.Pool) error {
	var database, currentUser string
	var ledgerCount, relationCount int
	var roleSafe bool
	err := pool.QueryRow(ctx, `
		SELECT current_database(), current_user,
		       (SELECT count(*) FROM public.schema_version WHERE migration_id = ANY($2::text[]) AND status = 'active'),
		       (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'context' AND table_name = ANY($1::text[])),
		       COALESCE((SELECT rolcanlogin AND NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
		                 AND pg_has_role('platform_runtime', 'context_import_writer', 'MEMBER')
		                 FROM pg_roles WHERE rolname = 'platform_runtime'), false)`, requiredContextTables, requiredMigrations).Scan(
		&database, &currentUser, &ledgerCount, &relationCount, &roleSafe,
	)
	if err != nil {
		return errors.New("uiw worker: verify platform schema: unavailable")
	}
	if database != "platform" {
		return fmt.Errorf("uiw worker: refusing database %q; platform is required", database)
	}
	if currentUser != "platform_runtime" {
		return fmt.Errorf("uiw worker: refusing database role %q; platform_runtime is required", currentUser)
	}
	if ledgerCount != len(requiredMigrations) || relationCount != len(requiredContextTables) || !roleSafe {
		return fmt.Errorf("uiw worker: platform schema admission failed: ledger=%d context_tables=%d/%d runtime_role_safe=%t", ledgerCount, relationCount, len(requiredContextTables), roleSafe)
	}
	return nil
}

var requiredContextTables = []string{
	"activity_execution", "activity_receipt", "hash_batch", "hash_batch_member",
	"hash_manifest", "hash_manifest_member", "hash_receipt", "normalization_lineage",
	"normalized_generation", "normalized_generation_publication", "normalized_record_identity",
	"raw_format_registry", "raw_generation", "raw_record_identity", "reconciliation_receipt",
	"retained_object", "source", "source_metadata", "source_version", "source_version_object",
	"uiw_preview_binding", "uiw_preview_snapshot", "uiw_preview_receipt", "uiw_preview_participant",
	"uiw_preview_message", "uiw_preview_attachment", "uiw_preview_event", "uiw_preview_decision",
	"repair_assessment", "repair_decision", "repair_resolution",
}

var requiredMigrations = []string{"0036", "0050", "0051"}
