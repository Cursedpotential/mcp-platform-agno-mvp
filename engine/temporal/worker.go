package temporal

import (
	"context"
	"errors"
)

// RunWorker is the retired partial-worker entry point. A worker that registers
// only two of UIW's 23 Activity names must never poll the same task queue as
// the production workflow. Use uiwworker.Run through
// cmd/universal-import-worker; this stub fails closed for any stale deployment
// still invoking engine/temporal/cmd/worker.
func RunWorker(_ context.Context, _ Config) error {
	return errors.New("temporal: partial universal-import worker retired; use cmd/universal-import-worker")
}
