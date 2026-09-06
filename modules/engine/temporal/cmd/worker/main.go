// Command proffer-worker runs the Temporal worker for
// engine/proffer.ProfferWorkflow's two n8n-backed Activities: it
// registers select_parser_activity and execute_parser_activity on one task
// queue and serves Activity tasks until interrupted.
//
// It owns no parsing, persistence, or HTTP-server logic of its own — see the
// engine/temporal package doc comment for what this binary does and
// deliberately does not do, and why it can run as a separate process from
// cmd/starter (the human preview hold is a real Temporal Signal/Query/Timer
// inside ProfferWorkflow, not in-process state either binary needs
// to share).
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	platformtemporal "github.com/Cursedpotential/probata/engine/temporal"
)

func main() {
	cfg, err := platformtemporal.LoadConfig()
	if err != nil {
		slog.Error("universal import worker configuration invalid", "error", err)
		os.Exit(1)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if err := platformtemporal.RunWorker(ctx, cfg); err != nil {
		slog.Error("universal import worker stopped", "error", err)
		os.Exit(1)
	}
}
