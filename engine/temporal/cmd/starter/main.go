// Command universal-import-starter exposes the small authenticated HTTP
// surface n8n's start/decision/preview workflows call, since n8n has no
// native Temporal client: start a UniversalImportWorkflow run, signal a
// human preview decision into a held run, and read back its preview state.
//
// It holds no parsing, persistence, or Activity logic of its own, and no
// in-process state shared with cmd/worker — Decide/Preview go through the
// Temporal server as a real Signal/Query against the workflow's own durable
// history, so this binary can run as a separate process (or many replicas)
// from the worker. See the engine/temporal package doc comment.
package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"go.temporal.io/sdk/client"

	platformtemporal "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/temporal"
)

const (
	defaultReadTimeout  = 10 * time.Second
	defaultWriteTimeout = 15 * time.Second
	defaultIdleTimeout  = 60 * time.Second
	gracefulStopTimeout = 20 * time.Second
)

func main() {
	if err := run(); err != nil {
		slog.Error("universal import starter stopped", "error", err)
		os.Exit(1)
	}
}

func run() error {
	cfg, err := platformtemporal.LoadConfig()
	if err != nil {
		return err
	}

	c, err := client.Dial(client.Options{
		HostPort:  cfg.TemporalHostPort,
		Namespace: cfg.TemporalNamespace,
	})
	if err != nil {
		return fmt.Errorf("dial temporal client: %w", err)
	}
	defer c.Close()

	starter, err := platformtemporal.NewWorkflowStarter(c, cfg.TemporalTaskQueue)
	if err != nil {
		return err
	}
	handler, err := platformtemporal.NewStarterHTTPHandler(starter, cfg.StarterToken)
	if err != nil {
		return err
	}

	server := &http.Server{
		Addr:              cfg.StarterAddr,
		Handler:           handler.Routes(),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       defaultReadTimeout,
		WriteTimeout:      defaultWriteTimeout,
		IdleTimeout:       defaultIdleTimeout,
	}

	shutdownContext, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	serveErrors := make(chan error, 1)
	go func() {
		slog.Info("universal import starter listening", "address", cfg.StarterAddr, "task_queue", cfg.TemporalTaskQueue)
		serveErrors <- server.ListenAndServe()
	}()
	select {
	case err := <-serveErrors:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-shutdownContext.Done():
		stopContext, cancel := context.WithTimeout(context.Background(), gracefulStopTimeout)
		defer cancel()
		return server.Shutdown(stopContext)
	}
}
