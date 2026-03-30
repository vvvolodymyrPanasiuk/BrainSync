# Classifier Skill: Note Classification Guidelines

## Task

Analyze the input text and return a JSON classification with these fields:
- `type`: one of `note`, `task`, `idea`, `journal`
- `topic`: the main subject/domain (e.g., "Architecture", "Backend", "Redis")
- `folder`: PascalCase vault folder name (e.g., "Architecture", "Tasks", "Ideas")
- `parent_moc`: MoC filename (e.g., "0 Architecture.md")
- `title`: concise 2–6 word title in the language of the input
- `confidence`: float 0.0–1.0 (how confident in the classification)

## Classification Rules

### Type Detection
- **note**: Contains concepts, learnings, facts ("дізнався", "виявив", "розумію", "learned", "found")
- **task**: Contains action items ("треба", "купити", "зробити", "need to", "buy", "fix", "implement")
- **idea**: Contains proposals, hypotheses ("а що якщо", "можна було б", "what if", "maybe we could")
- **journal**: Contains personal reflections, feelings, daily summaries ("сьогодні", "відчуваю", "today", "feel")

### Folder Selection
- Match to existing vault topics if possible (use the "Known topics" hint)
- Use PascalCase: `Architecture`, `Backend`, `Frontend`, `DevOps`, `Tasks`, `Ideas`, `Journal`
- Default folder: `General`
- Tasks always go to `Tasks` folder
- Journal entries go to `Journal` folder

### Confidence Scoring
- 0.9–1.0: Explicit command or very clear signal
- 0.7–0.9: Strong contextual signal
- 0.5–0.7: Moderate match
- Below 0.5: Uncertain — default to `note` type in `General`

## Response Format

Respond ONLY with valid JSON, no markdown, no explanation:
```json
{"type": "note", "topic": "CQRS", "folder": "Architecture", "parent_moc": "0 Architecture.md", "title": "CQRS розділяє read write", "confidence": 0.92}
```
