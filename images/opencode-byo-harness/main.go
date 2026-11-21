package main

import (
	"bufio"
	"bytes"
	"cmp"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"iter"
	"net/http"
	"os"
	"os/exec"
	"strings"
	"time"

	a2atype "github.com/a2aproject/a2a-go/v2/a2a"
	"github.com/a2aproject/a2a-go/v2/a2asrv"
	"github.com/kagent-dev/kagent/go/adk/pkg/app"
	"github.com/kagent-dev/kagent/go/adk/pkg/config"
	"github.com/kagent-dev/kagent/go/pkg/logging"
)

var errYieldStopped = errors.New("a2a stream consumer stopped")

type opencodeClient struct {
	url      string
	password string
	http     *http.Client
}

// startOpenCodeClient launches the v2 API server in --stdio mode and waits for
// it to report its URL on stdout. The server lives as long as ctx.
func startOpenCodeClient(ctx context.Context) (*opencodeClient, error) {
	secret := make([]byte, 16)
	if _, err := rand.Read(secret); err != nil {
		return nil, fmt.Errorf("opencode password: %w", err)
	}
	password := hex.EncodeToString(secret)

	cmd := exec.CommandContext(ctx, "opencode", "serve", "--stdio", "--hostname", "127.0.0.1")
	cmd.Dir = cmp.Or(os.Getenv("OPENCODE_WORKDIR"), "/workspace")
	cmd.Env = append(os.Environ(), "OPENCODE_PASSWORD="+password)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("opencode stdin: %w", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("opencode stdout: %w", err)
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("opencode serve start: %w", err)
	}
	// --stdio exits when stdin closes; keep it open until the process ends.
	go func() {
		<-ctx.Done()
		stdin.Close()
	}()

	type hello struct {
		URL string `json:"url"`
	}
	lineCh := make(chan string, 1)
	errCh := make(chan error, 1)
	go func() {
		s := bufio.NewScanner(stdout)
		if s.Scan() {
			lineCh <- s.Text()
			return
		}
		errCh <- fmt.Errorf("opencode serve closed stdout: %v", s.Err())
	}()
	select {
	case line := <-lineCh:
		var h hello
		if err := json.Unmarshal([]byte(line), &h); err != nil || h.URL == "" {
			return nil, fmt.Errorf("opencode serve hello %q: %v", line, err)
		}
		return &opencodeClient{
			url:      strings.TrimRight(h.URL, "/"),
			password: password,
			http:     &http.Client{},
		}, nil
	case err := <-errCh:
		return nil, err
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-time.After(15 * time.Second):
		return nil, fmt.Errorf("opencode serve startup timeout")
	}
}

func (c *opencodeClient) request(ctx context.Context, method, path string, body any) (*http.Response, error) {
	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		reader = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.url+path, reader)
	if err != nil {
		return nil, err
	}
	req.SetBasicAuth("opencode", c.password)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	return c.http.Do(req)
}

func (c *opencodeClient) call(ctx context.Context, method, path string, body any) error {
	resp, err := c.request(ctx, method, path, body)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(data)))
	}
	return nil
}

// sessionIDFor gives each A2A conversation a stable opencode session id, so
// context survives both multiple turns and harness restarts.
func sessionIDFor(contextID string) string {
	if contextID == "" {
		random := make([]byte, 12)
		_, _ = rand.Read(random)
		return "ses_" + hex.EncodeToString(random)
	}
	sum := sha256.Sum256([]byte(contextID))
	return "ses_" + hex.EncodeToString(sum[:12])
}

type apiEvent struct {
	Type string `json:"type"`
	Data struct {
		SessionID string `json:"sessionID"`
		Delta     string `json:"delta"`
		Error     struct {
			Type    string `json:"type"`
			Message string `json:"message"`
		} `json:"error"`
	} `json:"data"`
}

// streamOpenCode forwards each token-level text delta from the opencode v2
// event stream as soon as it arrives.
func streamOpenCode(ctx context.Context, c *opencodeClient, contextID, prompt string, onText func(string) error) error {
	if strings.TrimSpace(prompt) == "" {
		return fmt.Errorf("empty prompt")
	}
	sid := sessionIDFor(contextID)
	if err := c.call(ctx, http.MethodPost, "/api/session", map[string]any{"id": sid}); err != nil {
		return fmt.Errorf("opencode session: %w", err)
	}

	events, err := c.request(ctx, http.MethodGet, "/api/event", nil)
	if err != nil {
		return fmt.Errorf("opencode event stream: %w", err)
	}
	defer events.Body.Close()
	if events.StatusCode != http.StatusOK {
		return fmt.Errorf("opencode event stream: HTTP %d", events.StatusCode)
	}

	scanner := bufio.NewScanner(events.Body)
	scanner.Buffer(make([]byte, 64*1024), 8*1024*1024)
	// The first event (server.connected) confirms the subscription is live.
	if !scanner.Scan() {
		return fmt.Errorf("opencode event stream closed: %v", scanner.Err())
	}
	if err := c.call(ctx, http.MethodPost, "/api/session/"+sid+"/prompt", map[string]any{"text": prompt}); err != nil {
		return fmt.Errorf("opencode prompt: %w", err)
	}

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, "data:") {
			continue
		}
		var ev apiEvent
		if err := json.Unmarshal([]byte(strings.TrimSpace(strings.TrimPrefix(line, "data:"))), &ev); err != nil {
			continue
		}
		if ev.Data.SessionID != sid {
			continue
		}
		switch ev.Type {
		case "session.text.delta":
			if ev.Data.Delta != "" {
				if err := onText(ev.Data.Delta); err != nil {
					return err
				}
			}
		case "session.execution.succeeded", "session.idle":
			return nil
		case "session.execution.failed", "session.error":
			return fmt.Errorf("opencode: %s", cmp.Or(ev.Data.Error.Message, ev.Data.Error.Type, "unknown error"))
		}
	}
	if err := scanner.Err(); err != nil {
		return fmt.Errorf("opencode event read: %w", err)
	}
	return fmt.Errorf("opencode event stream ended before completion")
}

type executor struct {
	logger interface {
		Info(string, ...any)
		Error(string, ...any)
	}
	client *opencodeClient
}

func textFromMessage(msg *a2atype.Message) string {
	if msg == nil {
		return ""
	}
	var parts []string
	for _, p := range msg.Parts {
		if p == nil {
			continue
		}
		if t := strings.TrimSpace(p.Text()); t != "" {
			parts = append(parts, t)
		}
	}
	return strings.TrimSpace(strings.Join(parts, "\n"))
}

// artifactSink batches text deltas into one appendable A2A artifact.
type artifactSink struct {
	request *a2asrv.ExecutorContext
	yield   func(a2atype.Event, error) bool
	id      a2atype.ArtifactID
}

func (s *artifactSink) text(t string) bool {
	if t == "" {
		return true
	}
	var update *a2atype.TaskArtifactUpdateEvent
	if s.id == "" {
		update = a2atype.NewArtifactEvent(s.request, a2atype.NewTextPart(t))
		s.id = update.Artifact.ID
	} else {
		update = a2atype.NewArtifactUpdateEvent(s.request, s.id, a2atype.NewTextPart(t))
	}
	return s.yield(update, nil)
}

func (e executor) Execute(ctx context.Context, request *a2asrv.ExecutorContext) iter.Seq2[a2atype.Event, error] {
	return func(yield func(a2atype.Event, error) bool) {
		if !yield(a2atype.NewSubmittedTask(request, request.Message), nil) {
			return
		}
		if !yield(a2atype.NewStatusUpdateEvent(request, a2atype.TaskStateWorking, nil), nil) {
			return
		}

		sink := &artifactSink{request: request, yield: yield}
		onText := func(t string) error {
			if !sink.text(t) {
				return errYieldStopped
			}
			return nil
		}
		prompt := textFromMessage(request.Message)
		if err := streamOpenCode(ctx, e.client, request.ContextID, prompt, onText); err != nil {
			if errors.Is(err, errYieldStopped) {
				return
			}
			em := a2atype.NewMessage(a2atype.MessageRoleAgent, a2atype.NewTextPart(err.Error()))
			em.ContextID, em.TaskID = request.ContextID, request.TaskID
			yield(a2atype.NewStatusUpdateEvent(request, a2atype.TaskStateFailed, em), nil)
			return
		}
		if sink.id == "" && !sink.text("(no output)") {
			return
		}
		yield(a2atype.NewStatusUpdateEvent(request, a2atype.TaskStateCompleted, nil), nil)
	}
}

func (executor) Cancel(context.Context, *a2asrv.ExecutorContext) iter.Seq2[a2atype.Event, error] {
	return func(func(a2atype.Event, error) bool) {}
}

func main() {
	if err := config.MaterializeFromBootstrap(context.Background(), "/config"); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	compiled, err := config.LoadAgentConfig("/config/config.json")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	runtime := config.ProcessConfig(compiled)
	logger, err := logging.New(os.Stderr, cmp.Or(runtime.LogLevel, "info"))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	serverCtx, stopServer := context.WithCancel(context.Background())
	defer stopServer()
	client, err := startOpenCodeClient(serverCtx)
	if err != nil {
		logger.Error("failed to start opencode api server", "error", err)
		return
	}

	application, err := app.New(app.AppConfig{
		ControlPlaneURL:  runtime.ControlPlaneUrl,
		MaxContentLength: runtime.MaxContentLength,
		AgentCard: a2atype.AgentCard{
			Name:         cmp.Or(runtime.Name, "opencode-byo-stream"),
			Description:  "OpenCode BYO harness (token streaming)",
			Version:      "v1",
			Capabilities: a2atype.AgentCapabilities{Streaming: true},
		},
		Port:    fmt.Sprint(cmp.Or(runtime.GetPort(), 80)),
		AppName: cmp.Or(runtime.Name, "opencode-byo-stream"),
		Logger:  logger,
	}, executor{client: client})
	if err != nil {
		logger.Error("failed to create A2A application", "error", err)
		return
	}
	if err := application.Run(); err != nil {
		logger.Error("a2a application stopped", "error", err)
	}
}
