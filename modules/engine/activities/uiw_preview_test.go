package activities

import (
	"context"
	"errors"
	"testing"

	"github.com/Cursedpotential/probata/engine/proffer"
	"github.com/Cursedpotential/probata/engine/runtimeapi/previewmodel"
	"github.com/Cursedpotential/probata/engine/stagegraph"
)

type previewPublisherStub struct {
	binding previewmodel.Binding
	err     error
	got     proffer.PreviewPublicationRequest
}

func (s *previewPublisherStub) PublishWorkflowPreview(_ context.Context, request proffer.PreviewPublicationRequest) (previewmodel.Binding, error) {
	s.got = request
	return s.binding, s.err
}

func validPreviewPublicationRequest() proffer.PreviewPublicationRequest {
	receipts := make(map[string]proffer.Ref, len(previewmodel.ReceiptTypes))
	for _, kind := range previewmodel.ReceiptTypes {
		receipts[kind] = proffer.Ref(kind + "-receipt")
	}
	return proffer.PreviewPublicationRequest{
		RequestID: "request-1", SourceVersionRef: "source-1", RawGenerationRef: "raw-1",
		NormalizedGenerationRef: "normalized-1", ParserSelectionRef: "selection-1",
		ParserOptionsRef: "options-1", ReceiptRefs: receipts,
	}
}

func TestPreviewProjectionActivityPublishesReferenceOnlyRequest(t *testing.T) {
	store := &previewPublisherStub{binding: previewmodel.Binding{Handle: "opaque-handle", RequestID: "request-1"}}
	request := validPreviewPublicationRequest()
	got, err := (PreviewProjectionActivity{Store: store}).Publish(context.Background(), request)
	if err != nil {
		t.Fatal(err)
	}
	if got.Ref != "opaque-handle" || got.Stage != stagegraph.PublishPreview || store.got.NormalizedGenerationRef != request.NormalizedGenerationRef {
		t.Fatalf("result=%q request=%+v", got, store.got)
	}
}

func TestPreviewProjectionActivityFailsClosed(t *testing.T) {
	request := validPreviewPublicationRequest()
	request.ReceiptRefs["unknown"] = "receipt"
	if _, err := (PreviewProjectionActivity{Store: &previewPublisherStub{}}).Publish(context.Background(), request); err == nil {
		t.Fatal("unknown receipt type was accepted")
	}
	request = validPreviewPublicationRequest()
	delete(request.ReceiptRefs, previewmodel.ReceiptTypes[0])
	if _, err := (PreviewProjectionActivity{Store: &previewPublisherStub{}}).Publish(context.Background(), request); err == nil {
		t.Fatal("missing receipt was accepted")
	}
	request = validPreviewPublicationRequest()
	store := &previewPublisherStub{binding: previewmodel.Binding{Handle: "opaque-handle", RequestID: "another-request"}}
	if _, err := (PreviewProjectionActivity{Store: store}).Publish(context.Background(), request); err == nil {
		t.Fatal("uncorrelated binding was accepted")
	}
	store = &previewPublisherStub{err: errors.New("store unavailable")}
	if _, err := (PreviewProjectionActivity{Store: store}).Publish(context.Background(), request); !errors.Is(err, store.err) {
		t.Fatalf("store error = %v", err)
	}
}
