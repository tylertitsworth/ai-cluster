"""Tests for CLI argument parsing and override format."""

import pytest


class TestParseParams:
    def test_parses_key_value(self):
        from cli import _parse_params

        result = _parse_params(("count=5", "name=test"))
        assert result == {"count": 5, "name": "test"}

    def test_coerces_integers(self):
        from cli import _parse_params

        result = _parse_params(("count=5",))
        assert isinstance(result["count"], int)

    def test_coerces_floats(self):
        from cli import _parse_params

        result = _parse_params(("rate=0.5",))
        assert isinstance(result["rate"], float)

    def test_keeps_strings(self):
        from cli import _parse_params

        result = _parse_params(("name=hello world",))
        assert result["name"] == "hello world"


class TestParseAgentOverrides:
    def test_global_override_flat_format(self):
        from cli import _parse_agent_overrides

        result = _parse_agent_overrides(("model=gpt-5",))
        assert result == {"model": "gpt-5"}

    def test_agent_specific_override_uses_colon(self):
        from cli import _parse_agent_overrides

        result = _parse_agent_overrides(("investigator:model=gpt-5",))
        assert result == {"investigator:model": "gpt-5"}

    def test_mixed_overrides(self):
        from cli import _parse_agent_overrides

        result = _parse_agent_overrides((
            "model=global-model",
            "investigator:model=specific-model",
            "provider=openai",
        ))
        assert result == {
            "model": "global-model",
            "investigator:model": "specific-model",
            "provider": "openai",
        }

    def test_format_matches_providers_split_agent_overrides(self):
        """The CLI output format must match what providers._split_agent_overrides expects."""
        from cli import _parse_agent_overrides
        from engine.providers import _split_agent_overrides

        cli_output = _parse_agent_overrides((
            "model=global",
            "writer:model=writer-specific",
        ))

        effective = _split_agent_overrides(cli_output, "writer")
        assert effective["model"] == "writer-specific"

        effective_other = _split_agent_overrides(cli_output, "reviewer")
        assert effective_other["model"] == "global"


class TestRenderEvent:
    def test_token_event_uses_token_key(self):
        from cli import _render_event
        from rich.console import Console
        from io import StringIO

        buf = StringIO()
        con = Console(file=buf, force_terminal=True)
        color_map = {}

        event = {"type": "token", "agent": "writer", "token": "hello world"}
        _render_event(event, None, con, color_map)

        output = buf.getvalue()
        assert "hello world" in output

    def test_content_event_uses_content_key(self):
        from cli import _render_event
        from rich.console import Console
        from io import StringIO

        buf = StringIO()
        con = Console(file=buf, force_terminal=True)
        color_map = {}

        event = {"type": "content", "agent": "writer", "content": "full section"}
        _render_event(event, None, con, color_map)

        output = buf.getvalue()
        assert "full section" in output
