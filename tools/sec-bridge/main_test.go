package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestFetchProtocol(t *testing.T) {
	for _, status := range []int{200, 204, 400, 401, 403, 429, 503} {
		t.Run(http.StatusText(status), func(t *testing.T) {
			calls := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				calls++
				if r.Header.Get("Ocp-Apim-Subscription-Key") != "fixture-key" || r.URL.Query().Get("next_cursor") != "a+b=/" {
					t.Error("authentication or cursor changed")
				}
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(status)
				if status != 204 {
					_, _ = w.Write([]byte(`{"items":[{"last_val":12.3}],"next_cursor":"next"}`))
				}
			}))
			defer server.Close()
			got := fetch(request{Path: "/v2/fund/daily-info/nav", Params: map[string]string{"next_cursor": "a+b=/"}}, "fixture-key", server.URL)
			if got.Status != status || got.TransportError || calls != 1 {
				t.Fatalf("response=%+v calls=%d", got, calls)
			}
			if status == 200 && got.Body == "" {
				t.Fatal("missing JSON body")
			}
		})
	}
}

func TestRejectForeignPath(t *testing.T) {
	for _, path := range []string{"https://other.test", "/v2/fund/../secret", "/v2/fund/nav?key=x", "/v2/fund/%2e%2e/secret"} {
		if got := fetch(request{Path: path}, "fixture-key", ""); got.Status != 400 {
			t.Fatalf("accepted %q", path)
		}
	}
}
