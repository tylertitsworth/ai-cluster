package main

import (
	"bytes"
	"cmp"
	"context"
	"encoding/json"
	"fmt"
	"iter"
	"os"
	"os/exec"
	"strings"

	a2atype "github.com/a2aproject/a2a-go/v2/a2a"
	"github.com/a2aproject/a2a-go/v2/a2asrv"

	"github.com/kagent-dev/kagent/go/adk/pkg/app"
	"github.com/kagent-dev/kagent/go/adk/pkg/config"
	"github.com/kagent-dev/kagent/go/pkg/logging"
)

type executor struct {
	logger interface{ Info(string, ...any); Error(string, ...any) }
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

func runOpenCode(ctx context.Context, prompt string) (string, error) {
	if strings.TrimSpace(prompt) == "" {
		return "", fmt.Errorf("empty prompt")
	}
	args := []string{"run"}
	if m := os.Getenv("OPENCODE_MODEL"); m != "" {
		args = append(args, "--model", m)
	}
	if agent := os.Getenv("OPENCODE_AGENT"); agent != "" {
		args = append(args, "--agent", agent)
	}
	// auto-approve when requested/needed in non-interactive sandboxes
	if os.Getenv("OPENCODE_AUTO") != "false" {
		args = append(args, "--auto")
	}
	format := cmp.Or(os.Getenv("OPENCODE_FORMAT"), "default")
	args = append(args, "--format", format)
	args = append(args, prompt)

	cmd := exec.CommandContext(ctx, "opencode", args...)
	if dir := os.Getenv("OPENCODE_WORKDIR"); dir != "" {
		cmd.Dir = dir
	} else {
		cmd.Dir = "/workspace"
	}
	cmd.Env = os.Environ()
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	out := strings.TrimSpace(stdout.String())
	errOut := strings.TrimSpace(stderr.String())
	if err != nil {
		if out == "" {
			out = errOut
		}
		return out, fmt.Errorf("opencode run failed: %w: %s", err, errOut)
	}
	if format == "json" && out != "" {
		// best-effort: if JSON array/object events, try to extract last assistant text
		if s := extractFromJSON(out); s != "" {
			return s, nil
		}
	}
	if out == "" {
		out = errOut
	}
	return out, nil
}

func extractFromJSON(s string) string {
	s = strings.TrimSpace(s)
	// try array of events
	var arr []map[string]any
	if json.Unmarshal([]byte(s), &arr) == nil {
		for i := len(arr) - 1; i >= 0; i-- {
			if t, ok := findText(arr[i]); ok {
				return t
			}
		}
	}
	// try single object
	var obj map[string]any
	if json.Unmarshal([]byte(s), &obj) == nil {
		if t, ok := findText(obj); ok {
			return t
		}
	}
	// try line-delimited json
	lines := strings.Split(s, "\n")
	for i := len(lines) - 1; i >= 0; i-- {
		line := strings.TrimSpace(lines[i])
		if line == "" || !strings.HasPrefix(line, "{") {
			continue
		}
		var o map[string]any
		if json.Unmarshal([]byte(line), &o) == nil {
			if t, ok := findText(o); ok {
				return t
			}
		}
	}
	return ""
}

func findText(m map[string]any) (string, bool) {
	// common shapes: {type:"text", text:"..."}, {content:"..."}, {message:{content:...}}
	if t, ok := m["text"].(string); ok && strings.TrimSpace(t) != "" {
		return t, true
	}
	if t, ok := m["content"].(string); ok && strings.TrimSpace(t) != "" {
		return t, true
	}
	if msg, ok := m["message"].(map[string]any); ok {
		if t, ok := findText(msg); ok {
			return t, true
		}
	}
	if part, ok := m["part"].(map[string]any); ok {
		if t, ok := findText(part); ok {
			return t, true
		}
	}
	return "", false
}

func (e executor) Execute(ctx context.Context, request *a2asrv.ExecutorContext) iter.Seq2[a2atype.Event, error] {
	return func(yield func(a2atype.Event, error) bool) {
		if !yield(a2atype.NewSubmittedTask(request, request.Message), nil) {
			return
		}
		prompt := textFromMessage(request.Message)
		out, err := runOpenCode(ctx, prompt)
		if err != nil {
			msg := err.Error()
			if strings.TrimSpace(out) != "" {
				msg = out
			}
			em := a2atype.NewMessage(a2atype.MessageRoleAgent, a2atype.NewTextPart(msg))
			em.ContextID, em.TaskID = request.ContextID, request.TaskID
			yield(a2atype.NewStatusUpdateEvent(request, a2atype.TaskStateFailed, em), nil)
			return
		}
		if strings.TrimSpace(out) == "" {
			out = "(no output)"
		}
		message := a2atype.NewMessage(a2atype.MessageRoleAgent, a2atype.NewTextPart(out))
		message.ContextID, message.TaskID = request.ContextID, request.TaskID
		yield(a2atype.NewStatusUpdateEvent(request, a2atype.TaskStateCompleted, message), nil)
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
	application, err := app.New(app.AppConfig{
		ControlPlaneURL:  runtime.ControlPlaneUrl,
		MaxContentLength: runtime.MaxContentLength,
		AgentCard: a2atype.AgentCard{
			Name:         cmp.Or(runtime.Name, "opencode-byo"),
			Description:  "OpenCode BYO A2A harness",
			Version:      "v1",
			Capabilities: a2atype.AgentCapabilities{Streaming: true},
		},
		Port:    fmt.Sprint(cmp.Or(runtime.GetPort(), 80)),
		AppName: cmp.Or(runtime.Name, "opencode-byo"),
		Logger:  logger,
	}, executor{})
	if err != nil {
		logger.Error("failed to create A2A application", "error", err)
		return
	}
	if err := application.Run(); err != nil {
		logger.Error("a2a application stopped", "error", err)
	}
}
