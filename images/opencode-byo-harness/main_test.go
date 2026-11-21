package main

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

func fakeOpenCodeAPI(t *testing.T, sse string) *opencodeClient {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("/api/session", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("session method = %s, want POST", r.Method)
		}
		fmt.Fprint(w, `{"data":{}}`)
	})
	mux.HandleFunc("/api/session/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || !strings.HasSuffix(r.URL.Path, "/prompt") {
			t.Errorf("prompt request = %s %s", r.Method, r.URL.Path)
		}
		fmt.Fprint(w, `{"data":{}}`)
	})
	mux.HandleFunc("/api/event", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, sse)
		w.(http.Flusher).Flush()
	})
	srv := httptest.NewServer(mux)
	t.Cleanup(srv.Close)
	return &opencodeClient{url: srv.URL, password: "test", http: srv.Client()}
}

func TestStreamOpenCodeForwardsTextDeltas(t *testing.T) {
	sid := sessionIDFor("ctx-1")
	sse := fmt.Sprintf(`data: {"type":"server.connected","data":{}}

data: {"type":"session.text.delta","data":{"sessionID":%q,"delta":"first"}}

data: {"type":"session.text.delta","data":{"sessionID":"ses_other","delta":"ignored"}}

data: {"type":"session.text.delta","data":{"sessionID":%q,"delta":"second"}}

data: {"type":"session.execution.succeeded","data":{"sessionID":%q}}

`, sid, sid, sid)

	var got []string
	err := streamOpenCode(context.Background(), fakeOpenCodeAPI(t, sse), "ctx-1", "hi", func(s string) error {
		got = append(got, s)
		return nil
	})
	if err != nil {
		t.Fatalf("streamOpenCode: %v", err)
	}
	if want := []string{"first", "second"}; !reflect.DeepEqual(got, want) {
		t.Fatalf("chunks = %q, want %q", got, want)
	}
}

func TestStreamOpenCodeReturnsExecutionFailure(t *testing.T) {
	sid := sessionIDFor("ctx-2")
	sse := fmt.Sprintf(`data: {"type":"server.connected","data":{}}

data: {"type":"session.execution.failed","data":{"sessionID":%q,"error":{"type":"provider.free-limit","message":"limit reached"}}}

`, sid)

	err := streamOpenCode(context.Background(), fakeOpenCodeAPI(t, sse), "ctx-2", "hi", func(string) error { return nil })
	if err == nil || !strings.Contains(err.Error(), "limit reached") {
		t.Fatalf("err = %v, want free-usage-limit message", err)
	}
}

func TestSessionIDForIsStableAndNamespaced(t *testing.T) {
	if a, b := sessionIDFor("ctx-1"), sessionIDFor("ctx-1"); a != b {
		t.Fatalf("session id not stable: %q != %q", a, b)
	}
	if a, b := sessionIDFor("ctx-1"), sessionIDFor("ctx-2"); a == b {
		t.Fatalf("different contexts share session id %q", a)
	}
	if id := sessionIDFor("ctx-1"); !strings.HasPrefix(id, "ses_") {
		t.Fatalf("session id %q missing required prefix", id)
	}
}
