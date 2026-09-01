// Byline: Codex · GPT-5.6-Sol · 2026-08-30
package postgres

import (
	"context"
	"errors"
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
	row   probeRow
}

func (db *capturingProbeDB) QueryRow(_ context.Context, query string, _ ...any) pgx.Row {
	db.query = query
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

func TestProbeUIWSchemaHidesCatalogError(t *testing.T) {
	err := ProbeUIWSchema(context.Background(), probeDB{row: probeRow{err: errors.New("secret dsn detail")}})
	if err == nil || strings.Contains(err.Error(), "secret") {
		t.Fatalf("error = %v, want generic catalog failure", err)
	}
}
