# Telegram Bot Command Contracts

**Branch**: `001-brainsync-mvp` | **Date**: 2026-03-30

---

## Command Reference

| Command | Args | AI calls | Description |
|---------|------|----------|-------------|
| `/note <text>` | text | 0–2* | Save as note |
| `/task <text>` | text | 0 | Save as task (no classification) |
| `/idea <text>` | text | 0 | Save as idea (no classification) |
| `/journal <text>` | text | 0 | Save as journal entry |
| `/search <query>` | query | 0 | Full-text search vault |
| `/mode <mode>` | minimal\|balanced\|full | 0 | Change processing mode (persists to config.yaml) |
| `/status` | — | 0 | Show session stats and config summary |
| `/help` | — | 0 | List all commands |

*AI calls for `/note` depend on processing mode: minimal=0–1, balanced=1–2, full=2–3.
For all other explicit commands: 0 AI classification calls.

---

## Inline Prefix Alternatives

| Prefix | Language | Maps to |
|--------|----------|---------|
| `нотатка:` | UK | `/note` |
| `note:` | EN | `/note` |
| `задача:` | UK | `/task` |
| `task:` | EN | `/task` |
| `todo:` | EN | `/task` |
| `ідея:` | UK | `/idea` |
| `idea:` | EN | `/idea` |
| `день:` | UK | `/journal` |
| `journal:` | EN | `/journal` |

Prefix detection: case-insensitive match at start of message text.

---

## Response Formats

### Successful save confirmation
```
✓ Збережено → Architecture/0004 CQRS патерн.md
```

### Search results
```
🔍 Знайдено 3 нотатки для "Redis":

1. Architecture/0012 Redis кешування.md
   ...Redis використовується для кешування сесій...

2. Backend/0003 Redis Pub-Sub.md
   ...патерн Pub-Sub через Redis channels...
```

### No search results
```
Нічого не знайдено для "xyz"
```

### /status response
```
📊 BrainSync Status

Режим: balanced
Провайдер: anthropic (claude-sonnet-4-6)
Токени сесії: 1 240
Остання нотатка: Architecture/0004 CQRS патерн.md
Нотаток сьогодні: 3
Всього нотаток: 147
Контекст vault: 147 нотаток / ~3 200 токенів
```

### /mode confirmation
```
✓ Режим змінено на: full
⚠️ Набере чинності після перезапуску бота.
```

### AI failure fallback notification
```
⚠️ AI недоступний (rate limit). Нотатку збережено у minimal режимі.
→ Tasks/0023 Нотатка без класифікації.md
```

### Rate limit retry failure
```
⚠️ Telegram API тимчасово недоступний. Спробую ще раз пізніше.
```

---

## Security Rules

- Bot MUST NOT respond to any user ID not in `telegram.allowed_user_ids`
- Unauthorised attempts MUST be logged at `warn` level (user ID + timestamp only)
- Bot token MUST NOT appear in any response or log line
