// Byline: Codex · GPT-5.6 · 2026-08-29 (durable normalized UIW preview activity)
package activities

import (
	"context"
	"errors"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/runtimeapi/previewmodel"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

type PreviewProjectionPublisher interface {
	PublishWorkflowPreview(context.Context, uiw.PreviewPublicationRequest) (previewmodel.Binding, error)
}

type PreviewProjectionActivity struct{ Store PreviewProjectionPublisher }

func (a PreviewProjectionActivity) Publish(ctx context.Context, request uiw.PreviewPublicationRequest) (uiw.StageResult, error) {
	if a.Store == nil {
		return uiw.StageResult{}, errors.New("preview projection activity requires a durable store")
	}
	if strings.TrimSpace(request.RequestID) == "" || request.SourceVersionRef == "" || request.RawGenerationRef == "" || request.NormalizedGenerationRef == "" || request.ParserSelectionRef == "" || request.ParserOptionsRef == "" {
		return uiw.StageResult{}, errors.New("preview projection activity requires compact workflow/source/generation/parser refs")
	}
	for _, kind := range previewmodel.ReceiptTypes {
		if request.ReceiptRefs[kind] == "" {
			return uiw.StageResult{}, errors.New("preview projection activity requires all six receipt refs")
		}
	}
	if len(request.ReceiptRefs) != len(previewmodel.ReceiptTypes) {
		return uiw.StageResult{}, errors.New("preview projection activity refuses unknown receipt refs")
	}
	binding, err := a.Store.PublishWorkflowPreview(ctx, request)
	if err != nil {
		return uiw.StageResult{}, err
	}
	if strings.TrimSpace(binding.Handle) == "" || binding.RequestID != request.RequestID {
		return uiw.StageResult{}, errors.New("preview projection activity received an uncorrelated binding")
	}
	handle := uiw.Ref(binding.Handle)
	return uiw.StageResult{Stage: stagegraph.PublishPreview, Status: uiw.StatusSuccess, Ref: handle, ReceiptRef: handle}, nil
}
