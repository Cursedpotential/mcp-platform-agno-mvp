// Byline: Codex · GPT-5 · 2026-08-28 (authenticated Windows upload ingress)
package acquisition

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"strings"

	platformpostgres "github.com/Cursedpotential/probata/engine/postgres"
	"github.com/Cursedpotential/probata/engine/proffer"
)

// uploadRefScheme is the opaque acquisition-reference scheme minted for a
// staged Windows (or any authenticated HTTP client) upload. The VPS never
// mounts the submitting desktop's filesystem: bytes arrive over one
// authenticated POST, are sealed exactly like every other provider in this
// package, and the resulting content address becomes the Ref itself — the
// upload response and the acquisition reference are the same value, so
// there is nothing left to resolve except confirming the sealed object
// still exists and re-verifying its digest before retain_original_activity
// binds it.
const uploadRefScheme = "upload"

// UploadIngressConfig configures one tailnet-authorized HTTP upload endpoint.
type UploadIngressConfig struct {
	// Root is the seal root this ingress publishes into. It should be the
	// same root passed to other resolvers in this package (and may be the
	// same SOURCE_OBJECT_DIR the filesystem resolver already uses) so every
	// acquisition path shares one physical immutable object store.
	Root string
	// MaxBytes bounds one upload's body size. Required; there is no
	// unbounded default.
	MaxBytes int64
}

func (c UploadIngressConfig) validate() error {
	var problems []string
	if strings.TrimSpace(c.Root) == "" {
		problems = append(problems, "root is required")
	}
	if c.MaxBytes <= 0 {
		problems = append(problems, "max bytes must be positive")
	}
	if len(problems) > 0 {
		return fmt.Errorf("acquisition: upload ingress config invalid: %s", strings.Join(problems, "; "))
	}
	return nil
}

// UploadIngress is the Windows-submission acquisition endpoint: an
// authenticated HTTP handler a caller mounts on the platform's own API (this
// package does not start a server or own a route table). Staging bytes
// arrive over the wire from an authenticated client — never by the VPS
// reaching back into the submitting machine.
type UploadIngress struct {
	cfg UploadIngressConfig
}

// NewUploadIngress validates cfg and returns the handler. Root's seal
// directories are created (or verified) immediately so a misconfigured
// deployment fails at startup rather than on the first upload.
func NewUploadIngress(cfg UploadIngressConfig) (*UploadIngress, error) {
	if err := cfg.validate(); err != nil {
		return nil, err
	}
	if _, err := prepareSealRoot(cfg.Root); err != nil {
		return nil, err
	}
	return &UploadIngress{cfg: cfg}, nil
}

// uploadAcceptedResponse is the JSON body ServeHTTP returns on success. Ref
// is the exact proffer.Ref the client should submit as WorkflowInput.SourceRef.
type uploadAcceptedResponse struct {
	AcquisitionRef string `json:"acquisition_ref"`
	SHA256         string `json:"sha256"`
	ByteLength     int64  `json:"byte_length"`
}

// ServeHTTP implements http.Handler. Only POST is accepted; the body is
// bound to MaxBytes; the socket peer must be in the 100.64.0.0/10 tailnet
// range. Forwarded identity headers are ignored. On success it
// streams the request body straight into sealStream (single pass, no
// intermediate unbounded buffering) and returns the resulting acquisition
// registry.
func (u *UploadIngress) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	if !authorizedTailnetPeer(r) {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	r.Body = http.MaxBytesReader(w, r.Body, u.cfg.MaxBytes)
	sealed, err := sealStream(r.Context(), u.cfg.Root, r.Body)
	if err != nil {
		var maxBytesErr *http.MaxBytesError
		if errors.As(err, &maxBytesErr) {
			http.Error(w, "upload exceeds maximum accepted size", http.StatusRequestEntityTooLarge)
			return
		}
		http.Error(w, "upload could not be sealed", http.StatusBadGateway)
		return
	}

	response := uploadAcceptedResponse{
		AcquisitionRef: string(proffer.Ref(uploadRefScheme + "://" + hex.EncodeToString(sealed.ContentSHA256))),
		SHA256:         hex.EncodeToString(sealed.ContentSHA256),
		ByteLength:     sealed.ByteLength,
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	_ = json.NewEncoder(w).Encode(response)
}

func authorizedTailnetPeer(r *http.Request) bool {
	host, _, err := net.SplitHostPort(strings.TrimSpace(r.RemoteAddr))
	if err != nil {
		return false
	}
	ip := net.ParseIP(host).To4()
	return ip != nil && ip[0] == 100 && ip[1] >= 64 && ip[1] <= 127
}

// NewUploadIngressResolver resolves "upload://<sha256-hex>" acquisition
// references minted by UploadIngress.ServeHTTP. Because the upload endpoint
// already sealed the object under its content address, resolution is a
// durability check, not a second copy: it locates the previously published
// object and re-hashes it, so a corrupted or tampered object between upload
// and retain_original_activity fails closed instead of silently binding bad
// bytes.
func NewUploadIngressResolver(root string) (platformpostgres.ImmutableAcquisitionResolver, error) {
	if strings.TrimSpace(root) == "" {
		return nil, errors.New("acquisition: upload ingress resolver root is required")
	}
	if _, err := prepareSealRoot(root); err != nil {
		return nil, err
	}
	return func(ctx context.Context, ref proffer.Ref) (platformpostgres.ImmutableAcquisition, error) {
		if err := ctx.Err(); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		digestHex, err := parseUploadRef(ref)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		objectPath, err := digestObjectPath(root, digestHex)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		info, err := os.Stat(objectPath)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: locate uploaded object %s: %w", digestHex, err)
		}
		digestBytes, err := hex.DecodeString(digestHex)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: decode uploaded object digest: %w", err)
		}
		if err := verifyObject(ctx, objectPath, digestBytes, info.Size()); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		return platformpostgres.ImmutableAcquisition{
			StorageClass:  storageClassSealed,
			ObjectURI:     fileURI(objectPath),
			ContentSHA256: digestBytes,
			ByteLength:    info.Size(),
		}, nil
	}, nil
}

func parseUploadRef(ref proffer.Ref) (string, error) {
	value := strings.TrimSpace(string(ref))
	const prefix = uploadRefScheme + "://"
	if !strings.HasPrefix(value, prefix) {
		return "", fmt.Errorf("acquisition: upload acquisition reference must be %s<sha256-hex>", prefix)
	}
	digestHex := strings.ToLower(strings.TrimPrefix(value, prefix))
	if len(digestHex) != sha256.Size*2 {
		return "", errors.New("acquisition: upload acquisition reference digest must be 64 hex characters")
	}
	return digestHex, nil
}
