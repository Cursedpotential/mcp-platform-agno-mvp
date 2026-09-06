package runtimeapi

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/Cursedpotential/probata/engine/activities"
	"github.com/Cursedpotential/probata/engine/parser"
)

func TestRouterHealthReadinessAndAuthenticatedCapabilities(t *testing.T) {
	registry, err := parser.NewRegistry(httpTestAdapter{})
	if err != nil {
		t.Fatal(err)
	}
	handler, err := NewParserActivityHandler(activities.ParserActivities{Registry: registry, Store: httpTestStore{}}, "test-token")
	if err != nil {
		t.Fatal(err)
	}
	capability := httpTestAdapter{}.Capability()
	router, err := NewRouter(handler, []parser.Capability{capability}, func(context.Context) error { return nil })
	if err != nil {
		t.Fatal(err)
	}
	for _, path := range []string{HealthPath, ReadinessPath} {
		recorder := httptest.NewRecorder()
		router.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, path, nil))
		if recorder.Code != http.StatusOK {
			t.Fatalf("%s status = %d, body = %s", path, recorder.Code, recorder.Body.String())
		}
		if recorder.Header().Get("Cache-Control") != "no-store" {
			t.Fatalf("%s omitted no-store response policy", path)
		}
	}

	unauthorized := httptest.NewRecorder()
	router.ServeHTTP(unauthorized, httptest.NewRequest(http.MethodGet, CapabilitiesPath, nil))
	if unauthorized.Code != http.StatusUnauthorized {
		t.Fatalf("unauthorized capability status = %d", unauthorized.Code)
	}
	authorized := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, CapabilitiesPath, nil)
	request.Header.Set("Authorization", "Bearer test-token")
	router.ServeHTTP(authorized, request)
	if authorized.Code != http.StatusOK {
		t.Fatalf("capability status = %d, body = %s", authorized.Code, authorized.Body.String())
	}
}

func TestRouterReadinessDoesNotExposeDependencyError(t *testing.T) {
	registry, err := parser.NewRegistry(httpTestAdapter{})
	if err != nil {
		t.Fatal(err)
	}
	handler, err := NewParserActivityHandler(activities.ParserActivities{Registry: registry, Store: httpTestStore{}}, "test-token")
	if err != nil {
		t.Fatal(err)
	}
	router, err := NewRouter(handler, []parser.Capability{httpTestAdapter{}.Capability()}, func(context.Context) error {
		return errors.New("postgres://user:secret@example.invalid/platform")
	})
	if err != nil {
		t.Fatal(err)
	}
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, ReadinessPath, nil))
	if recorder.Code != http.StatusServiceUnavailable {
		t.Fatalf("readiness status = %d", recorder.Code)
	}
	if body := recorder.Body.String(); body == "" || containsSecret(body) {
		t.Fatalf("readiness response exposed dependency detail: %s", body)
	}
}

func containsSecret(value string) bool {
	return strings.Contains(value, "secret")
}
