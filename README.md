# 🧠 BrainSync

> Local AI-powered personal knowledge management — capture thoughts from Telegram, structure them with Claude AI, save to Obsidian vault.

BrainSync — це фонова служба, яка перетворює сирі думки з Telegram на структуровані нотатки в Obsidian. Ти пишеш у бот — він класифікує, форматує і зберігає нотатку у правильній папці з frontmatter, MoC-посиланнями та wikilinks. Все локально, крім AI API.

---

## Можливості

- **Telegram → Obsidian**: пишеш думку в бот — отримуєш структуровану `.md` нотатку
- **AI-класифікація**: Claude автоматично визначає тип (note / task / idea / journal), тему і папку
- **Три режими обробки**: `minimal` (0–1 AI виклики), `balanced` (1–2), `full` (2–3 + wikilinks)
- **MoC (Map of Content)**: автоматичне оновлення індексних файлів при додаванні нотаток
- **Пошук**: `/search Redis` — повнотекстовий пошук по vault без AI
- **Scheduled summaries**: щоденний / тижневий / місячний огляд у Telegram
- **Git sync**: автоматичний commit і push до remote після кожної нотатки
- **MCP server**: `vault_writer/server.py` реєструється як MCP сервер у Claude Code
- **Inline prefixes**: `задача: купити молоко` без команди — автовизначення типу

---

## Швидкий старт

### Вимоги

- Python 3.12+
- Git
- Obsidian vault (наприклад, `C:\SecondaryBrain`)
- [Telegram bot token](https://t.me/BotFather)
- [Anthropic API key](https://console.anthropic.com)
- Твій Telegram user ID ([@userinfobot](https://t.me/userinfobot))

### Встановлення

```bash
# 1. Клонуй репозиторій
git clone https://github.com/vvvolodymyrPanasiuk/BrainSync.git
cd BrainSync

# 2. Створи virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Unix

# 3. Встанови залежності
pip install -r requirements.txt

# 4. Запусти інсталятор
python setup.py
```

Інсталятор запитає vault path, токен бота, user ID, API key, режим обробки та git налаштування — і згенерує `config.yaml`.

### Запуск

```bash
# Windows
start.bat

# Unix
bash start.sh

# Або напряму
python main.py
```

Бот запускається у foreground. `Ctrl+C` — зупинити.

---

## Команди бота

| Команда | Опис |
|---------|------|
| `/note <текст>` | Зберегти нотатку |
| `/task <текст>` | Зберегти задачу |
| `/idea <текст>` | Зберегти ідею |
| `/journal <текст>` | Запис у щоденник |
| `/search <запит>` | Пошук по vault |
| `/mode minimal\|balanced\|full` | Змінити режим обробки |
| `/status` | Статус бота і статистика |
| `/help` | Список команд |

**Inline prefixes** (без команди):

```
нотатка: ...    note: ...
задача: ...     task: ...     todo: ...
ідея: ...       idea: ...
день: ...       journal: ...
```

Будь-який текст без префікса → AI-класифікація автоматично.

---

## Архітектура

```
BrainSync/
│
├── main.py                        # Entry point: запускає Telegram bot
├── setup.py                       # Інтерактивний інсталятор
├── start.bat / start.sh           # Launch scripts
│
├── config/
│   └── loader.py                  # Парсинг config.yaml → AppConfig dataclasses
│                                  # Валідація, logging setup, get_ai_provider()
│
├── vault_writer/                  # Ядро системи (shared library)
│   ├── server.py                  # MCP server (окремий процес, stdio transport)
│   │
│   ├── ai/
│   │   ├── provider.py            # AIProvider ABC + ProcessingMode enum
│   │   ├── anthropic_provider.py  # AnthropicProvider (claude-sonnet-4-6)
│   │   ├── ollama_provider.py     # OllamaProvider stub (v1.1)
│   │   ├── classifier.py          # classify() → ClassificationResult
│   │   ├── formatter.py           # format_note() → markdown body
│   │   └── enricher.py            # add_wikilinks() (full mode)
│   │
│   ├── vault/
│   │   ├── writer.py              # write_note(), update_moc(), sequential numbering
│   │   ├── reader.py              # read_frontmatter(), read_note_content()
│   │   └── indexer.py             # build_index(), update_index() → VaultIndex
│   │
│   └── tools/                     # MCP tool handlers
│       ├── create_note.py         # Головний orchestrator (classify→format→enrich→write→MoC)
│       ├── search_notes.py        # Повнотекстовий пошук (0 AI calls)
│       ├── classify_content.py    # Класифікація тексту
│       ├── update_moc.py          # Оновлення Map of Content
│       └── get_vault_index.py     # Snapshot vault index
│
├── telegram/
│   ├── bot.py                     # PTB Application setup + job queue
│   ├── formatter.py               # Форматування повідомлень (Ukrainian)
│   └── handlers/
│       ├── commands.py            # /note /task /idea /journal /search /mode /status /help
│       ├── message.py             # Plain-text handler + prefix detection + RetryAfter
│       └── schedule.py            # Daily/weekly/monthly summary jobs
│
├── git_sync/
│   └── sync.py                    # commit_note() + push_if_due()
│
└── .brain/
    ├── AGENTS.md                  # Universal AI instructions
    └── skills/
        ├── vault-writer.md        # Folder naming, numbering, MoC rules
        ├── classifier.md          # Classification guidelines + JSON format
        └── obsidian-rules.md      # Frontmatter, tags, wikilink syntax
```

### Потік даних: від повідомлення до нотатки

```
Telegram message
       │
       ▼
  auth_check()          ← відхиляє неавторизованих
       │
       ▼
  detect_prefix()       ← "задача:" → NoteType.TASK (0 AI calls)
       │
       ▼
  [if no prefix]
  classify()            ← AI call #1: тип + папка + заголовок
       │
       ▼
  [if balanced/full]
  format_note()         ← AI call #2: структурований markdown body
       │
       ▼
  [if full]
  add_wikilinks()       ← AI call #3: wikilinks з vault index
       │
       ▼
  write_note()          ← запис файлу (threading.Lock)
       │
       ▼
  create_moc_if_missing()
  update_moc()          ← оновлення "## 🔑 Main sections"
       │
       ▼
  update_index()        ← O(1) оновлення VaultIndex
       │
       ▼
  commit_note()         ← git commit (якщо enabled)
       │
       ▼
  "✓ Збережено → Architecture/0004 CQRS патерн.md"
```

### Два незалежних процеси

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│   main.py (Telegram bot)    │     │  vault_writer/server.py      │
│                             │     │  (MCP server)                │
│  - run_polling()            │     │  - stdio transport           │
│  - handlers                 │     │  - 5 MCP tools               │
│  - scheduled jobs           │     │  - launched by Claude Code   │
│                             │     │                              │
│  imports vault_writer/      │     │  imports vault_writer/       │
│  as Python library          │     │  as Python library           │
└─────────────────────────────┘     └──────────────────────────────┘
```

> **Чому два процеси?** MCP stdio transport захоплює stdin/stdout — несумісно з PTB `run_polling()` в одному процесі. Обидва компоненти імпортують `vault_writer/` напряму як Python library без IPC.

---

## Конфігурація (`config.yaml`)

Генерується автоматично через `python setup.py`. Ніколи не комітується в git.

### AI

```yaml
ai:
  provider: "anthropic"           # "anthropic" | "ollama" (ollama — v1.1)
  model: "claude-sonnet-4-6"      # Anthropic model ID
  ollama_url: "http://localhost:11434"
  processing_mode: "balanced"     # "minimal" | "balanced" | "full"
  agents_file: ".brain/AGENTS.md" # Інструкції для AI
  skills_path: ".brain/skills/"   # Папка зі skills
  inject_vault_index: true        # Передавати список тем AI при класифікації
  max_context_tokens: 4000        # Ліміт токенів для vault context
  api_key: ""                     # ⚠️ НІКОЛИ не логується і не комітується
```

**Режими обробки:**

| Режим | AI виклики | Що робить |
|-------|-----------|-----------|
| `minimal` | 0–1 | Класифікація (або нічого якщо є префікс) |
| `balanced` | 1–2 | Класифікація + форматування |
| `full` | 2–3 | Класифікація + форматування + wikilinks |

Змінити без перезапуску: `/mode balanced` — записує в `config.yaml`, набирає чинності після рестарту.

### Vault

```yaml
vault:
  path: "C:\\SecondaryBrain"      # Абсолютний шлях до Obsidian vault
  language: "uk"                  # Мова нотаток для AI prompts
```

### Enrichment

```yaml
enrichment:
  add_wikilinks: true             # Додавати wikilinks (тільки full mode)
  update_moc: true                # Оновлювати MoC при кожній нотатці
  max_related_notes: 5            # Максимум wikilinks у full mode
  scan_vault_on_start: true       # Rebuild vault index при запуску
```

### Telegram

```yaml
telegram:
  bot_token: ""                   # ⚠️ НІКОЛИ не логується
  allowed_user_ids: [123456789]   # Тільки ці user ID можуть писати боту
```

> Якщо `allowed_user_ids` порожній — бот відхиляє всі повідомлення і логує WARNING.

### Prefixes

```yaml
prefixes:
  note:    ["нотатка:", "note:"]
  task:    ["задача:", "task:", "todo:"]
  idea:    ["ідея:", "idea:"]
  journal: ["день:", "journal:"]
```

Кастомізуй під себе — регістр ігнорується при матчингу.

### Git

```yaml
git:
  enabled: true
  auto_commit: true
  commit_message: "vault: auto-save {date} {time}"
  push_remote: true
  remote: "origin"
  branch: "main"
  push_interval_minutes: 30       # Пуш не частіше раз на 30 хв
```

Push з silent failure — якщо remote недоступний, бот продовжує роботу.

### Schedule

```yaml
schedule:
  daily_summary:
    enabled: true
    time: "21:00"                 # HH:MM local time
  weekly_review:
    enabled: true
    day: "sunday"
    time: "20:00"
  monthly_review:
    enabled: true
    day: 1                        # День місяця: 1–28
    time: "10:00"
```

Щоденний підсумок містить нотатки за сьогодні + відкриті задачі (`- [ ] ...`).
Тижневий — кількість нотаток по темах за тиждень.
Місячний — нотатки цього місяця + нові теми.

### Logging

```yaml
logging:
  level: "info"                   # "debug" | "info" | "warn" | "error"
  log_to_file: true
  log_path: "logs/vault.log"
  log_ai_decisions: true          # Логує: тип + папка + confidence (БЕЗ тексту нотатки)
```

---

## Реєстрація як MCP сервер у Claude Code

Додай до `.claude/mcp_servers.json` в будь-якому проекті:

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

Доступні MCP інструменти:

| Tool | Опис |
|------|------|
| `create_note` | Створити нотатку (classify → format → write → MoC) |
| `search_notes` | Пошук по vault |
| `classify_content` | Класифікувати текст |
| `update_moc` | Оновити Map of Content |
| `get_vault_index` | Отримати snapshot vault index |

---

## Формат нотаток у vault

```markdown
---
title: "CQRS патерн"
date: 2026-03-30
categories: [Architecture]
tags: [areas/architecture, types/notes]
MoC: "[[0 Architecture]]"
---

## Description

CQRS (Command Query Responsibility Segregation) розділяє моделі читання і запису...

## Conclusions

Використовувати коли read і write мають різні вимоги до продуктивності.

## Links

- [[0003 Event Sourcing]]
- [[0001 DDD основи]]
```

**Іменування файлів:** `NNNN Title.md` — 4-цифровий порядковий номер у межах папки.
**MoC файли:** `0 TopicName.md` — завжди на початку папки.

---

## Безпека

- `config.yaml` в `.gitignore` — ніколи не потрапляє в репозиторій
- `api_key` і `bot_token` ніколи не логуються і не передаються в AI prompts
- `log_ai_decisions` логує лише `type`, `folder`, `confidence` — без тексту нотаток
- Бот відповідає тільки user ID зі списку `allowed_user_ids`
- Неавторизовані спроби логуються на рівні `warn`

---

## Залежності

| Пакет | Версія | Призначення |
|-------|--------|-------------|
| `python-telegram-bot` | ≥20.0 | Async Telegram bot + job scheduler |
| `anthropic` | latest | Claude AI SDK |
| `mcp` | latest | Model Context Protocol server |
| `pyyaml` | latest | Читання/запис config.yaml |
| `gitpython` | latest | Git операції у vault |
| `pytest` | latest | Тести |
