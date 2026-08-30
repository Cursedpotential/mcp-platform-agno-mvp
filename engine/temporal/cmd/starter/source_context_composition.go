package main

import (
	"errors"
	"net/http"
)

// mountSourceContextRoutes adds the actor-bound metadata receipt surface
// without changing the Temporal starter's legacy route ownership.
func mountSourceContextRoutes(existing, sourceContext http.Handler) (http.Handler, error) {
	if existing == nil || sourceContext == nil {
		return nil, errors.New("source context routes require existing and source context handlers")
	}
	mux := http.NewServeMux()
	mux.Handle("POST /reference-import/source-contexts", sourceContext)
	mux.Handle("/", existing)
	return mux, nil
}
