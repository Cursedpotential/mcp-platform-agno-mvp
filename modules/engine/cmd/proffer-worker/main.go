// Command proffer-worker runs the sole production worker for
// engine/proffer.ProfferWorkflow and all 23 of its atomic Activities.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/Cursedpotential/probata/engine/profferworker"
)

func main() {
	cfg, err := profferworker.LoadConfig()
	if err != nil {
		slog.Error("universal import worker configuration invalid", "error", err)
		os.Exit(1)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := profferworker.Run(ctx, cfg); err != nil {
		slog.Error("universal import worker stopped", "error", err)
		os.Exit(1)
	}
}
