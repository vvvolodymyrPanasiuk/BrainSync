"""Claude Code CLI provider — delegates completions to `claude -p` via stdin.

Supports both native Anthropic and Ollama backends:
  provider: claude_code
  model: claude-sonnet-4-6          # native Anthropic
  claude_code_use_ollama: false

  provider: claude_code
  model: kimi-k2.5:cloud            # Ollama backend
  claude_code_use_ollama: true
  ollama_url: http://localhost:11434

Claude Code's built-in tools (web search, bash, file I/O, MCP servers) are
available automatically — no custom tool wiring needed.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from vault_writer.ai.provider import AIProvider

logger = logging.getLogger(__name__)

# Cached claude invocation command (computed once)
_CLAUDE_CMD: list[str] | None = None


def _resolve_claude_cmd() -> list[str]:
    """Return the command list needed to invoke the Claude Code CLI.

    On Windows, `claude` is a Node.js `.cmd` wrapper that can't receive stdin
    directly through subprocess — so we locate the underlying JS entry point
    and invoke `node <cli.js>` instead.
    """
    global _CLAUDE_CMD
    if _CLAUDE_CMD is not None:
        return _CLAUDE_CMD

    path = shutil.which("claude")
    if path is None:
        raise RuntimeError(
            "Claude Code CLI ('claude') not found in PATH.\n"
            "Install it from https://claude.ai/download"
        )

    if sys.platform == "win32" and path.lower().endswith((".cmd", ".bat")):
        # e.g. C:\nvm4w\nodejs\claude.cmd
        # The .cmd wraps: node <dp0>\node_modules\@anthropic-ai\claude-code\cli.js
        dp0 = Path(path).parent
        cli_js = dp0 / "node_modules" / "@anthropic-ai" / "claude-code" / "cli.js"
        if cli_js.exists():
            node = shutil.which("node") or "node"
            _CLAUDE_CMD = [node, str(cli_js)]
            logger.debug("claude resolved: node %s", cli_js)
            return _CLAUDE_CMD

    _CLAUDE_CMD = [path]
    return _CLAUDE_CMD


class ClaudeCodeProvider(AIProvider):
    """AI provider that uses the Claude Code CLI as its runtime.

    The subprocess inherits all Claude Code capabilities: web search, file
    access, bash execution, MCP tools, and any skills/AGENTS.md in the
    project tree.
    """

    def __init__(
        self,
        model: str,
        use_ollama: bool = False,
        ollama_url: str = "http://localhost:11434",
        project_dir: str | None = None,
        timeout: int = 300,
    ) -> None:
        self._model = model
        self._use_ollama = use_ollama
        self._ollama_url = ollama_url.rstrip("/")
        self._project_dir = project_dir or str(Path.cwd())
        self._timeout = timeout

    # ── Environment ───────────────────────────────────────────────────────────

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        if self._use_ollama:
            # Ollama exposes an Anthropic-compatible Messages API
            env["ANTHROPIC_AUTH_TOKEN"] = "ollama"
            env["ANTHROPIC_API_KEY"] = "ollama"
            env["ANTHROPIC_BASE_URL"] = self._ollama_url
        return env

    # ── Core completion ───────────────────────────────────────────────────────

    def complete(self, prompt: str, max_tokens: int = 1000) -> str:
        """Pipe prompt to `claude -p` via stdin and return response text."""
        base_cmd = _resolve_claude_cmd()
        cmd = base_cmd + ["-p", "--dangerously-skip-permissions", "--output-format", "text"]
        if self._model:
            cmd.extend(["--model", self._model])

        logger.debug(
            "ClaudeCodeProvider: model=%s prompt_len=%d use_ollama=%s",
            self._model, len(prompt), self._use_ollama,
        )

        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._build_env(),
                cwd=self._project_dir,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError(
                f"Claude Code CLI timed out after {self._timeout}s — "
                "consider increasing ai.claude_code_timeout in config.yaml"
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Claude Code CLI not found: {exc}\n"
                "Install from https://claude.ai/download"
            )

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[:400]
            raise RuntimeError(
                f"claude CLI exited with code {result.returncode}.\n"
                f"stderr: {stderr}"
            )

        return result.stdout.strip()

    def complete_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        media_type: str,
        max_tokens: int = 1000,
    ) -> str:
        """Image input via CLI stdin is not supported — falls back to text."""
        logger.warning(
            "ClaudeCodeProvider: image input not supported via CLI, "
            "falling back to text-only completion"
        )
        return self.complete(prompt, max_tokens)

    # ── Warmup ────────────────────────────────────────────────────────────────

    def warmup(self) -> None:
        """Verify that the claude CLI is installed and the backend responds."""
        # 1. Resolve command (raises if not found)
        base_cmd = _resolve_claude_cmd()

        # 2. Check version
        try:
            ver = subprocess.run(
                base_cmd + ["--version"],
                capture_output=True,
                text=True,
                timeout=15,
                env=self._build_env(),
            )
            version_str = (ver.stdout or ver.stderr or "").strip()
            logger.info(
                "ClaudeCodeProvider warmup: %s | model=%s use_ollama=%s",
                version_str, self._model, self._use_ollama,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Claude Code CLI not found: {exc}\n"
                "Install: https://claude.ai/download\n"
                "Then verify: claude --version"
            )

        # 3. Quick ping to confirm model responds
        try:
            reply = self.complete("Reply with exactly: OK", max_tokens=10)
            if not reply:
                raise ValueError("Empty response from model during warmup")
            logger.info("ClaudeCodeProvider: model '%s' is responsive", self._model)
        except Exception as exc:
            raise RuntimeError(
                f"Claude Code warmup failed for model '{self._model}'.\n"
                f"Error: {exc}\n\n"
                + (
                    "If using Ollama, make sure:\n"
                    f"  1. ollama serve is running\n"
                    f"  2. ollama pull {self._model}\n"
                    f"  3. ollama_url in config.yaml is correct"
                    if self._use_ollama else
                    "Check your ANTHROPIC_API_KEY environment variable."
                )
            )

    # ── Model listing (Ollama only) ───────────────────────────────────────────

    def list_models(self) -> list[str]:
        """Return available Ollama models (empty list for native Anthropic)."""
        if not self._use_ollama:
            return []
        try:
            import json, urllib.request
            url = self._ollama_url + "/api/tags"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
            return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            logger.debug("ClaudeCodeProvider.list_models: %s", exc)
            return []
