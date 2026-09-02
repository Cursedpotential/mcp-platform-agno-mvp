// Byline: Codex · GPT-5.6-Sol · 2026-08-30
// Extended · Claude Code · Sonnet 5 · 2026-09-02 (BUILD LANE S2): ledger
// retarget coverage (public.schema_version -> ops.migration_ledger, D-109).
// Extended · Claude Code · Sonnet 5 · 2026-09-02 (BUILD LANE S3, D-126):
// dev-bypass sentinel-identity gating coverage.
package postgres

import (
	"bytes"
	"context"
	"errors"
	"log/slog"
	"strings"
	"testing"

	"github.com/jackc/pgx/v5"
)

type probeDB struct{ row probeRow }

func (db probeDB) QueryRow(context.Context, string, ...any) pgx.Row {
	return db.row
}

type capturingProbeDB struct {
	query string
	args  []any
	row   probeRow
}

func (db *capturingProbeDB) QueryRow(_ context.Context, query string, args ...any) pgx.Row {
	db.query = query
	db.args = args
	return db.row
}

type probeRow struct {
	database, user, owner                                                 string
	ledger, tables, columns                                               int
	constraintsExact, substrateExact, roleSafe, grantsExact, receiptExact bool
	err                                                                   error
}

func (row probeRow) Scan(dest ...any) error {
	if row.err != nil {
		return row.err
	}
	*dest[0].(*string), *dest[1].(*string), *dest[2].(*string) = row.database, row.user, row.owner
	*dest[3].(*int), *dest[4].(*int), *dest[5].(*int) = row.ledger, row.tables, row.columns
	*dest[6].(*bool), *dest[7].(*bool), *dest[8].(*bool), *dest[9].(*bool), *dest[10].(*bool) =
		row.constraintsExact, row.substrateExact, row.roleSafe, row.grantsExact, row.receiptExact
	return nil
}

func admittedProbeRow() probeRow {
	return probeRow{
		database: "platform", user: "platform_runtime", owner: "platform_admin",
		ledger: len(requiredUIWMigrations), tables: len(requiredUIWTables), columns: len(requiredUIWColumns),
		constraintsExact: true, substrateExact: true, roleSafe: true, grantsExact: true, receiptExact: true,
	}
}

func TestProbeUIWSchemaAdmitsExactPlatformContract(t *testing.T) {
	if err := ProbeUIWSchema(context.Background(), probeDB{row: admittedProbeRow()}); err != nil {
		t.Fatal(err)
	}
}

func TestProbeUIWSchemaCastsCatalogNamesBeforeTextArrayComparison(t *testing.T) {
	db := &capturingProbeDB{row: admittedProbeRow()}
	if err := ProbeUIWSchema(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	if strings.Count(db.query, "a.attname::text") != 3 || strings.Contains(db.query, "ARRAY(SELECT a.attname FROM") {
		t.Fatal("catalog attribute arrays must be text[] before comparison with the required text[] contract")
	}
}

func TestProbeUIWSchemaRejectsLegacy0043Substitution(t *testing.T) {
	row := admittedProbeRow()
	row.ledger--
	err := ProbeUIWSchema(context.Background(), probeDB{row: row})
	if err == nil || !strings.Contains(err.Error(), "ledger=8/9") {
		t.Fatalf("error = %v, want missing-0054 admission failure", err)
	}
}

// TestProbeUIWSchemaLedgerQueriesTheRealLedger locks in D-109: the ledger
// check must read ops.migration_ledger (sql/0055 PART 5, the actual ledger,
// no status column -- presence means applied) and must never again read
// public.schema_version (a data-contract version table that only resembles
// a ledger; that resemblance destroyed migration state once already,
// 2026-08-29). Regression guard for the BUILD LANE S2 retarget.
func TestProbeUIWSchemaLedgerQueriesTheRealLedger(t *testing.T) {
	db := &capturingProbeDB{row: admittedProbeRow()}
	if err := ProbeUIWSchema(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	// Executable SQL only -- comments are allowed (and expected) to explain
	// the D-109 history by naming the retired table, so strip "--" line
	// comments before asserting what the query actually executes.
	var executable strings.Builder
	for _, line := range strings.Split(db.query, "\n") {
		if idx := strings.Index(line, "--"); idx >= 0 {
			line = line[:idx]
		}
		executable.WriteString(line)
		executable.WriteByte('\n')
	}
	code := executable.String()
	if !strings.Contains(code, "FROM ops.migration_ledger") {
		t.Fatal("ledger check must query ops.migration_ledger, the real migration ledger (D-109)")
	}
	if strings.Contains(code, "public.schema_version") {
		t.Fatal("ledger check must not reference public.schema_version, which is not a migration ledger (D-109)")
	}
	if !strings.Contains(code, "has_table_privilege('platform_runtime','ops.migration_ledger','INSERT')") {
		t.Fatal("write-safety guard must assert platform_runtime lacks INSERT on the real ledger, ops.migration_ledger")
	}
}

func TestProbeUIWSchemaRejectsWrongIdentityOrScope(t *testing.T) {
	for name, mutate := range map[string]func(*probeRow){
		"legacy database": func(row *probeRow) { row.database = "ai" },
		"wrong role":      func(row *probeRow) { row.user = "ai" },
		"wrong owner":     func(row *probeRow) { row.owner = "ai" },
		"bad fk":          func(row *probeRow) { row.constraintsExact = false },
		"bad substrate":   func(row *probeRow) { row.substrateExact = false },
		"excess grant":    func(row *probeRow) { row.grantsExact = false },
		"missing receipt": func(row *probeRow) { row.receiptExact = false },
	} {
		t.Run(name, func(t *testing.T) {
			row := admittedProbeRow()
			mutate(&row)
			if err := ProbeUIWSchema(context.Background(), probeDB{row: row}); err == nil {
				t.Fatal("expected fail-closed admission")
			}
		})
	}
}

// TestProbeUIWSchemaDefaultBindsStrictAuthoritativeIdentity locks in the
// fail-closed default (D-125, D-126): with PLATFORM_DEV_AUTH_BYPASS unset,
// the probe must bind the REAL authoritative identity and the STRICT
// (approved_by='owner') receipt expectation -- unmet until go-live, exactly
// as before this build lane.
func TestProbeUIWSchemaDefaultBindsStrictAuthoritativeIdentity(t *testing.T) {
	db := &capturingProbeDB{row: admittedProbeRow()}
	if err := ProbeUIWSchema(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	if len(db.args) != 14 {
		t.Fatalf("expected 14 bound query args, got %d", len(db.args))
	}
	if db.args[3] != authoritativeMatterID || db.args[4] != authoritativeCourtCaseID {
		t.Fatalf("flag unset must bind the real authoritative identity, got matter=%v court_case=%v", db.args[3], db.args[4])
	}
	if db.args[11] != registryReceiptPayloadByteLength || db.args[12] != registryReceiptApprovedBy || db.args[13] != registryReceiptApprovedOn {
		t.Fatalf("flag unset must bind the STRICT receipt expectation, got payload_byte_length=%v approved_by=%v approved_on=%v",
			db.args[11], db.args[12], db.args[13])
	}
}

// TestProbeUIWSchemaDevBypassBindsSentinelIdentityNotSkipsIt is the D-126
// regression guard for the owner's exact correction: the flag must not turn
// identity/receipt checking OFF, it must repoint both checks at the fixed
// DEV sentinel. If this ever regresses into a bypass that removes the
// predicates rather than retargeting them, this test fails.
func TestProbeUIWSchemaDevBypassBindsSentinelIdentityNotSkipsIt(t *testing.T) {
	t.Setenv("PLATFORM_DEV_AUTH_BYPASS", "1")
	db := &capturingProbeDB{row: admittedProbeRow()}
	if err := ProbeUIWSchema(context.Background(), db); err != nil {
		t.Fatal(err)
	}
	if len(db.args) != 14 {
		t.Fatalf("expected 14 bound query args, got %d", len(db.args))
	}
	if db.args[3] != devMatterID || db.args[4] != devCourtCaseID {
		t.Fatalf("PLATFORM_DEV_AUTH_BYPASS=1 must bind the DEV sentinel identity, got matter=%v court_case=%v", db.args[3], db.args[4])
	}
	if db.args[12] != devReceiptApprovedBy {
		t.Fatalf("PLATFORM_DEV_AUTH_BYPASS=1 must bind the honest dev receipt label, got approved_by=%v", db.args[12])
	}
	if db.args[12] == registryReceiptApprovedBy {
		t.Fatal("dev-mode approved_by must never equal 'owner' (D-126: no fabricated owner-approval receipt)")
	}
	// The query text itself must be byte-identical between modes -- only the
	// bound constants move. This is what makes it a retarget, not a skip.
	strictDB := &capturingProbeDB{row: admittedProbeRow()}
	// t.Setenv above is still in effect for this subtest scope; unset for
	// the strict-mode capture by clearing the variable explicitly.
	t.Setenv("PLATFORM_DEV_AUTH_BYPASS", "")
	if err := ProbeUIWSchema(context.Background(), strictDB); err != nil {
		t.Fatal(err)
	}
	if db.query != strictDB.query {
		t.Fatal("dev-bypass mode must run the identical query text as strict mode -- only bound values may differ")
	}
}

// TestProbeUIWSchemaDevBypassLogsLoudWarning: D-125/D-126 both require a
// loud one-line warning naming the flag whenever the bypass is active.
func TestProbeUIWSchemaDevBypassLogsLoudWarning(t *testing.T) {
	t.Setenv("PLATFORM_DEV_AUTH_BYPASS", "true")
	var buf bytes.Buffer
	previous := slog.Default()
	slog.SetDefault(slog.New(slog.NewTextHandler(&buf, nil)))
	t.Cleanup(func() { slog.SetDefault(previous) })

	if err := ProbeUIWSchema(context.Background(), probeDB{row: admittedProbeRow()}); err != nil {
		t.Fatal(err)
	}
	logged := buf.String()
	if !strings.Contains(logged, "PLATFORM_DEV_AUTH_BYPASS") {
		t.Fatalf("dev-bypass admission must log a warning naming the flag, got: %s", logged)
	}
	if !strings.Contains(strings.ToUpper(logged), "WARN") {
		t.Fatalf("dev-bypass admission warning must be logged at WARN level, got: %s", logged)
	}
}

// TestProbeUIWSchemaDevBypassEnvSpellings covers the truthy/falsy env
// vocabulary devAuthBypassEnabled accepts, including the fail-closed default.
func TestProbeUIWSchemaDevBypassEnvSpellings(t *testing.T) {
	cases := map[string]bool{
		"":        false,
		"0":       false,
		"false":   false,
		"no":      false,
		"off":     false,
		"garbage": false,
		"1":       true,
		"true":    true,
		"TRUE":    true,
		"  1  ":   true,
		"yes":     true,
		"on":      true,
	}
	for value, want := range cases {
		t.Run("value="+value, func(t *testing.T) {
			t.Setenv("PLATFORM_DEV_AUTH_BYPASS", value)
			db := &capturingProbeDB{row: admittedProbeRow()}
			if err := ProbeUIWSchema(context.Background(), db); err != nil {
				t.Fatal(err)
			}
			gotDev := db.args[3] == devMatterID
			if gotDev != want {
				t.Fatalf("PLATFORM_DEV_AUTH_BYPASS=%q: dev-mode active = %t, want %t", value, gotDev, want)
			}
		})
	}
}

func TestProbeUIWSchemaHidesCatalogError(t *testing.T) {
	err := ProbeUIWSchema(context.Background(), probeDB{row: probeRow{err: errors.New("secret dsn detail")}})
	if err == nil || strings.Contains(err.Error(), "secret") {
		t.Fatalf("error = %v, want generic catalog failure", err)
	}
}
