// Byline: Codex · GPT-5.6 · 2026-08-29 (durable normalized Proffer preview activity)
package activities

import (
	"context"
	"errors"
	"strings"

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/runtimeapi/previewmodel"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

type PreviewProjectionPublisher interface {
	PublishWorkflowPreview(context.Context, proffer.PreviewPublicationRequest) (previewmodel.Binding, error)
}

type PreviewProjectionActivity struct{ Store PreviewProjectionPublisher }

func (a PreviewProjectionActivity) Publish(ctx context.Context, request proffer.PreviewPublicationRequest) (proffer.StageResult, error) {
	if a.Store == nil {
		return proffer.StageResult{}, errors.New("preview projection activity requires a durable store")
	}
	if strings.TrimSpace(request.RequestID) == "" || request.SourceVersionRef == "" || request.RawGenerationRef == "" || request.NormalizedGenerationRef == "" || request.ParserSelectionRef == "" || request.ParserOptionsRef == "" {
		return proffer.StageResult{}, errors.New("preview projection activity requires compact workflow/source/generation/parser refs")
	}
	for _, kind := range previewmodel.ReceiptTypes {
		if request.ReceiptRefs[kind] == "" {
			return proffer.StageResult{}, errors.New("preview projection activity requires all six receipt refs")
		}
	}
	if len(request.ReceiptRefs) != len(previewmodel.ReceiptTypes) {
		return proffer.StageResult{}, errors.New("preview projection activity refuses unknown receipt refs")
	}
	binding, err := a.Store.PublishWorkflowPreview(ctx, request)
	if err != nil {
		return proffer.StageResult{}, err
	}
	if strings.TrimSpace(binding.Handle) == "" || binding.RequestID != request.RequestID {
		return proffer.StageResult{}, errors.New("preview projection activity received an uncorrelated binding")
	}
	handle := proffer.Ref(binding.Handle)
	return proffer.StageResult{Stage: stagegraph.PublishPreview, Status: proffer.StatusSuccess, Ref: handle, ReceiptRef: handle}, nil
}
