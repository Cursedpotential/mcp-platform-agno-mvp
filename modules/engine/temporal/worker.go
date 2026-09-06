package temporal

import (
	"context"
	"errors"
)

// RunWorker is the retired partial-worker entry point. A worker that registers
// only two of Proffer's 26 Activity names must never poll the same task queue as
// the production workflow. Use profferworker.Run through
// cmd/proffer-worker; this stub fails closed for any stale deployment
// still invoking engine/temporal/cmd/worker.
func RunWorker(_ context.Context, _ Config) error {
	return errors.New("temporal: partial proffer worker retired; use cmd/proffer-worker")
}
