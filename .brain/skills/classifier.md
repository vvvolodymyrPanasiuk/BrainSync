# Classifier Skill: Note Classification Guidelines

## Task

Analyze the input text and return a JSON classification with these fields:
- `type`: one of `note`, `task`, `idea`, `journal`
- `topic`: the main subject/domain (e.g., "Programming", "Trading")
- `folder`: full vault folder path up to 4 levels (e.g., "Learning/Programming/Python")
- `parent_moc`: MoC filename based on innermost folder (e.g., "0 Python.md")
- `title`: concise 2–6 word title in the configured locale
- `confidence`: float 0.0–1.0 (how confident in the classification)

## Folder Path Structure

Folders follow a hierarchy: `GeneralCategory/Topic[/Subtopic][/Section]`
- **GeneralCategory**: broad life domain (e.g. "Learning", "Business", "Personal", "Projects", "Health", "Finance", "Creative")
- **Topic**: specific subject within the category (e.g. "Programming", "Trading", "Cooking")
- **Subtopic** (optional): narrower area (e.g. "Python", "Indicators", "Boxing")
- **Section** (optional): even narrower (e.g. "Algorithms", "Basics")

Minimum depth: 2 levels. Maximum: 4 levels. Use the minimum needed.

## Classification Rules

### Type Detection
- **note**: Contains concepts, learnings, facts
- **task**: Contains action items ("need to", "buy", "fix", "implement", "do")
- **idea**: Contains proposals, hypotheses ("what if", "maybe we could", "idea:")
- **journal**: Contains personal reflections, feelings, daily summaries

### Confidence Scoring
- 0.9–1.0: Explicit command or very clear signal
- 0.7–0.9: Strong contextual signal
- 0.5–0.7: Moderate match
- Below 0.5: Uncertain — default to `note` type in `General`

## Response Format

Respond ONLY with valid JSON, no markdown, no explanation:
```json
{"type": "note", "topic": "CQRS", "folder": "Learning/Programming", "parent_moc": "0 Programming.md", "title": "CQRS separates read and write", "confidence": 0.92}
```
