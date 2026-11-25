package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path"
	"runtime/debug"
	"strings"
	"time"

	sec "github.com/jwitmann/sec-go"
)

type request struct {
	Path           string            `json:"path"`
	Params         map[string]string `json:"params"`
	TimeoutSeconds int               `json:"timeout_seconds"`
}

type response struct {
	Status         int    `json:"status"`
	ContentType    string `json:"content_type"`
	RetryAfter     string `json:"retry_after"`
	Body           string `json:"body"`
	TransportError bool   `json:"transport_error,omitempty"`
}

func fetch(in request, key, baseURL string) response {
	out := response{}
	if !strings.HasPrefix(in.Path, "/v2/fund/") || path.Clean(in.Path) != in.Path || strings.ContainsAny(in.Path, "?#%\\") {
		out.Status = 400
		return out
	}
	if key == "" {
		out.Status = 401
		return out
	}
	if in.TimeoutSeconds <= 0 || in.TimeoutSeconds > 300 {
		in.TimeoutSeconds = 60
	}
	opts := []sec.Option{
		sec.WithTimeout(time.Duration(in.TimeoutSeconds) * time.Second),
		sec.WithMaxRetries(0), // Python owns retries, pagination and persistent cache.
		sec.WithRequestHook(func(req *http.Request) {
			req.Header.Set("Accept", "application/json")
			req.Header.Set("User-Agent", "thai-stock-quote/sec-bridge")
		}),
		sec.WithResponseHook(func(_ *http.Request, resp *http.Response, _ error) {
			if resp != nil {
				out.Status = resp.StatusCode
				out.ContentType = resp.Header.Get("Content-Type")
				out.RetryAfter = resp.Header.Get("Retry-After")
			}
		}),
	}
	if baseURL != "" {
		opts = append(opts, sec.WithBaseURL(strings.TrimRight(baseURL, "/")))
	}
	client, err := sec.NewClient(key, opts...)
	if err != nil {
		out.TransportError = true
		return out
	}
	query := url.Values{}
	for k, v := range in.Params {
		query.Set(k, v)
	}
	endpoint := in.Path
	if len(query) > 0 {
		endpoint += "?" + query.Encode()
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(in.TimeoutSeconds)*time.Second)
	defer cancel()
	data, err := client.Get(ctx, endpoint)
	if errors.Is(err, sec.ErrNotFound) && out.Status == 204 {
		return out
	}
	if err != nil {
		var apiError *sec.APIError
		if errors.As(err, &apiError) {
			out.Status = apiError.StatusCode
		} else {
			out.TransportError = true
		}
		return out
	}
	out.Body = string(data)
	return out
}

func version() map[string]string {
	out := map[string]string{}
	if info, ok := debug.ReadBuildInfo(); ok {
		for _, dep := range info.Deps {
			if dep.Path == "github.com/jwitmann/sec-go" && dep.Replace != nil {
				out["module"] = dep.Replace.Path
				out["version"] = dep.Replace.Version
			}
		}
	}
	return out
}

func main() {
	encoder := json.NewEncoder(os.Stdout)
	if len(os.Args) == 2 && os.Args[1] == "--version" {
		_ = encoder.Encode(version())
		return
	}
	var in request
	if err := json.NewDecoder(io.LimitReader(os.Stdin, 1<<20)).Decode(&in); err != nil {
		fmt.Fprintln(os.Stderr, "invalid bridge request")
		os.Exit(2)
	}
	if err := encoder.Encode(fetch(in, os.Getenv("SEC_API_KEY"), os.Getenv("SEC_API_BASE_URL"))); err != nil {
		os.Exit(2)
	}
}
