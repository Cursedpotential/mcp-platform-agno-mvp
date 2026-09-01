// Command universal-import-worker runs the sole production worker for
// engine/uiw.UniversalImportWorkflow and all 23 of its atomic Activities.
package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiwworker"
)

func main() {
	cfg, err := uiwworker.LoadConfig()
	if err != nil {
		slog.Error("universal import worker configuration invalid", "error", err)
		os.Exit(1)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := uiwworker.Run(ctx, cfg); err != nil {
		slog.Error("universal import worker stopped", "error", err)
		os.Exit(1)
	}
}
