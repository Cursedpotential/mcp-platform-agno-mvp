// Byline: Codex · GPT-5 · 2026-08-28 (object-storage acquisition resolver)
package acquisition

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"

	platformpostgres "github.com/Cursedpotential/mcp-platform-agno-mvp/engine/postgres"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

// ObjectStorageConfig names one S3-compatible account the acquisition
// boundary is authorized to read from. Cloudflare R2 and Backblaze B2 both
// speak the S3 API, so the same struct and the same fetch path in this file
// serve either provider; only the endpoint, region, and credentials differ,
// and callers supply all three — nothing here is a compiled-in endpoint or
// credential. Zero-value fields fail validate() closed.
type ObjectStorageConfig struct {
	// Endpoint is the provider's S3-compatible endpoint, e.g.
	// "https://<accountid>.r2.cloudflarestorage.com" for R2 or
	// "https://s3.<region>.backblazeb2.com" for B2. Required.
	Endpoint string
	// Region is required by SigV4 signing even when the provider does not
	// use AWS regions; R2 accepts "auto".
	Region          string
	AccessKeyID     string
	SecretAccessKey string
	// SessionToken is optional; most R2/B2 static credentials do not use one.
	SessionToken string
	// UsePathStyle selects <endpoint>/<bucket>/<key> addressing instead of
	// <bucket>.<endpoint>/<key>. Both providers' own documentation
	// recommends path style; it also avoids requiring bucket-name-safe DNS
	// labels. Defaults to true via the provider constructors below.
	UsePathStyle bool
}

func (c ObjectStorageConfig) validate(label string) error {
	var problems []string
	if strings.TrimSpace(c.Endpoint) == "" {
		problems = append(problems, "endpoint is required")
	}
	if strings.TrimSpace(c.Region) == "" {
		problems = append(problems, "region is required")
	}
	if strings.TrimSpace(c.AccessKeyID) == "" {
		problems = append(problems, "access key id is required")
	}
	if strings.TrimSpace(c.SecretAccessKey) == "" {
		problems = append(problems, "secret access key is required")
	}
	if len(problems) > 0 {
		return fmt.Errorf("acquisition: %s object storage config invalid: %s", label, strings.Join(problems, "; "))
	}
	return nil
}

// objectStorageGetter is the minimal S3 surface this package depends on, so
// tests can substitute a fake client instead of a live bucket.
type objectStorageGetter interface {
	GetObject(context.Context, *s3.GetObjectInput, ...func(*s3.Options)) (*s3.GetObjectOutput, error)
}

// NewCloudflareR2AcquisitionResolver resolves acquisition references of the
// form "r2://<bucket>/<key>" against one Cloudflare R2 account and seals
// the fetched object into root using the same content-addressed layout
// every other resolver in this package uses.
func NewCloudflareR2AcquisitionResolver(root string, cfg ObjectStorageConfig) (platformpostgres.ImmutableAcquisitionResolver, error) {
	if err := cfg.validate("Cloudflare R2"); err != nil {
		return nil, err
	}
	if !cfg.UsePathStyle {
		cfg.UsePathStyle = true
	}
	return newObjectStorageAcquisitionResolver(root, "r2", newS3Client(cfg))
}

// NewBackblazeB2AcquisitionResolver resolves acquisition references of the
// form "b2://<bucket>/<key>" against one Backblaze B2 account's S3-
// compatible API endpoint, sealed identically to the R2 resolver above.
func NewBackblazeB2AcquisitionResolver(root string, cfg ObjectStorageConfig) (platformpostgres.ImmutableAcquisitionResolver, error) {
	if err := cfg.validate("Backblaze B2"); err != nil {
		return nil, err
	}
	if !cfg.UsePathStyle {
		cfg.UsePathStyle = true
	}
	return newObjectStorageAcquisitionResolver(root, "b2", newS3Client(cfg))
}

func newS3Client(cfg ObjectStorageConfig) *s3.Client {
	awsCfg := aws.Config{
		Region: cfg.Region,
		Credentials: credentials.NewStaticCredentialsProvider(
			cfg.AccessKeyID, cfg.SecretAccessKey, cfg.SessionToken,
		),
	}
	endpoint := cfg.Endpoint
	usePathStyle := cfg.UsePathStyle
	return s3.NewFromConfig(awsCfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(endpoint)
		o.UsePathStyle = usePathStyle
	})
}

// newObjectStorageAcquisitionResolver is the single provider-neutral core
// both the R2 and B2 constructors call. scheme names the opaque Ref prefix
// this resolver instance answers for ("r2" or "b2"); it never reaches the
// object-storage account itself, only the reference format.
func newObjectStorageAcquisitionResolver(root, scheme string, client objectStorageGetter) (platformpostgres.ImmutableAcquisitionResolver, error) {
	if strings.TrimSpace(root) == "" {
		return nil, errors.New("acquisition: object storage resolver root is required")
	}
	if client == nil {
		return nil, errors.New("acquisition: object storage client is required")
	}
	if _, err := prepareSealRoot(root); err != nil {
		return nil, err
	}
	return func(ctx context.Context, ref uiw.Ref) (platformpostgres.ImmutableAcquisition, error) {
		if err := ctx.Err(); err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		bucket, key, err := parseObjectStorageRef(scheme, ref)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, err
		}
		out, err := client.GetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(bucket), Key: aws.String(key)})
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: fetch %s object %s/%s: %w", scheme, bucket, key, err)
		}
		defer out.Body.Close()

		sealed, err := sealStream(ctx, root, out.Body)
		if err != nil {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf("acquisition: seal %s object %s/%s: %w", scheme, bucket, key, err)
		}
		if out.ContentLength != nil && *out.ContentLength != sealed.ByteLength {
			return platformpostgres.ImmutableAcquisition{}, fmt.Errorf(
				"acquisition: %s object %s/%s reported %d bytes but %d were sealed",
				scheme, bucket, key, *out.ContentLength, sealed.ByteLength,
			)
		}
		return sealed, nil
	}, nil
}

// parseObjectStorageRef requires the exact "<scheme>://<bucket>/<key>"
// shape. Refs are opaque outside this package, but internally the scheme
// must match the resolver instance answering it — a filesystem resolver
// combined into the same dispatch table (dispatch.go) must never see an
// r2:// or b2:// ref, and this resolver must never see anything else.
func parseObjectStorageRef(scheme string, ref uiw.Ref) (bucket, key string, err error) {
	value := strings.TrimSpace(string(ref))
	if value == "" {
		return "", "", fmt.Errorf("acquisition: %s acquisition reference is empty", scheme)
	}
	parsed, parseErr := url.Parse(value)
	if parseErr != nil {
		return "", "", fmt.Errorf("acquisition: parse %s acquisition reference: %w", scheme, parseErr)
	}
	if !strings.EqualFold(parsed.Scheme, scheme) {
		return "", "", fmt.Errorf("acquisition: acquisition reference scheme %q does not match %s resolver", parsed.Scheme, scheme)
	}
	bucket = parsed.Host
	key = strings.TrimPrefix(parsed.Path, "/")
	if bucket == "" || key == "" {
		return "", "", fmt.Errorf("acquisition: %s acquisition reference must be %s://<bucket>/<key>", scheme, scheme)
	}
	if unescaped, unescapeErr := url.PathUnescape(key); unescapeErr == nil {
		key = unescaped
	}
	return bucket, key, nil
}

// objectStorageRef builds an opaque acquisition Ref for the given scheme,
// bucket, and key. It is exported for callers (the Windows upload handler's
// counterpart, ingest CLIs, or n8n's upstream fetch step) that need to mint
// a Ref this package's resolvers can consume without hand-assembling the
// URI format themselves.
func objectStorageRef(scheme, bucket, key string) uiw.Ref {
	return uiw.Ref(fmt.Sprintf("%s://%s/%s", scheme, bucket, strings.TrimPrefix(key, "/")))
}

// CloudflareR2Ref mints an opaque r2:// acquisition reference for the given
// bucket and object key.
func CloudflareR2Ref(bucket, key string) uiw.Ref { return objectStorageRef("r2", bucket, key) }

// BackblazeB2Ref mints an opaque b2:// acquisition reference for the given
// bucket and object key.
func BackblazeB2Ref(bucket, key string) uiw.Ref { return objectStorageRef("b2", bucket, key) }
