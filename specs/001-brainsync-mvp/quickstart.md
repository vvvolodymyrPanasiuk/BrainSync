# Quickstart: BrainSync MVP

**Branch**: `001-brainsync-mvp` | **Date**: 2026-03-30

---

## Prerequisites

- Python 3.12+
- Git installed and configured
- An existing Obsidian vault (e.g. `C:\SecondaryBrain`)
- A Telegram bot token (create via [@BotFather](https://t.me/BotFather))
- Anthropic API key (from console.anthropic.com)
- Your Telegram user ID (get from [@userinfobot](https://t.me/userinfobot))

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/youruser/BrainSync.git
cd BrainSync

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

**requirements.txt** will include:
- `python-telegram-bot>=20.0`
- `anthropic`
- `mcp`
- `pyyaml`
- `gitpython`
- `pytest` (dev)

---

## First-Time Setup

```bash
python setup.py
```

The interactive installer will ask for:
1. Vault path (e.g. `C:\SecondaryBrain`)
2. Telegram bot token
3. Your Telegram user ID
4. AI provider (`anthropic` or skip for manual config later)
5. Anthropic API key (if anthropic selected)
6. Processing mode (`minimal` / `balanced` / `full`)
7. Git sync enabled? (y/n)
8. Git remote URL (if yes)

On completion, `setup.py` will:
- Generate `config.yaml`
- Create `.brain/AGENTS.md` and `.brain/skills/` from templates
- Index the vault
- Test Telegram connection (send test message to your chat)
- Test AI provider connection
- Generate `start.bat` (Windows) and `start.sh` (Unix)
- Start the bot

---

## Starting the Bot

```bash
# Windows
start.bat

# or directly:
.venv\Scripts\activate
python main.py
```

The bot runs in the foreground. Press `Ctrl+C` to stop.

---

## Using the Bot

Send messages to your Telegram bot:

```
дізнався що CQRS розділяє read і write моделі
→ ✓ Збережено → Architecture/0004 CQRS патерн.md

/task купити молоко
→ ✓ Збережено → Tasks/0012 купити молоко.md

/search Redis
→ 🔍 Знайдено 2 нотатки...

/mode full
→ ✓ Режим змінено на: full (після перезапуску)

/status
→ 📊 BrainSync Status...
```

---

## Registering as Claude Code MCP Server

Add to your project's `.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "vault-writer": {
      "command": "python",
      "args": ["C:/Projects/BrainSync/vault_writer/server.py"]
    }
  }
}
```

Then use from Claude Code:
```
create a note about the CQRS architecture decision we just made
```

---

## Validation Checklist

After setup, verify:

- [ ] Bot replies to your Telegram message
- [ ] A `.md` file appears in the vault with correct frontmatter
- [ ] Parent MoC is updated with a new wikilink
- [ ] Git commit created in vault repository (if enabled)
- [ ] `/status` returns correct info
- [ ] `/search <query>` returns results from vault

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| Bot not responding | Verify `telegram.allowed_user_ids` contains your ID |
| `vault path not found` | Verify `vault.path` in `config.yaml` exists |
| AI calls failing | Check `ai.api_key` in `config.yaml`; check network |
| Git push failing | Run `git remote -v` in vault dir; check credentials |
| MoC not updating | Verify `enrichment.update_moc: true` in config |
| Vault index empty | Set `enrichment.scan_vault_on_start: true` and restart |
