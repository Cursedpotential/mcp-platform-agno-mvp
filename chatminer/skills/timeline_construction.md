# Skill: Timeline Construction

## Purpose
Build a unified chronological timeline from extracted events across
all conversations, handling date ambiguity and merging sources.

## When to Use
- After extracting events from personal/legal segments
- Building the case timeline for court
- Cross-referencing events across multiple chat sources

## Timeline Event Format
```json
{
  "event_id": "uuid",
  "date": "2023-04-15T22:40:00",
  "date_confidence": "HIGH",
  "date_source": "explicit_timestamp",
  "description": "Incident at Hilton Garden Inn",
  "source_conversations": ["conv-uuid-1", "conv-uuid-2"],
  "people": ["Matt Salem", "Katrina Kinzel"],
  "location": "Hilton Garden Inn, Portland, OR",
  "evidence_refs": ["hotel_receipt.pdf", "timeline_2023.json"],
  "emotional_context": "terrified, felt trapped",
  "verbatim_quotes": ["I didn't know what to do"],
  "topic_tags": ["personal_legal", "evidence"]
}
```

## Date Handling

### Explicit Dates (HIGH confidence)
- "April 15, 2023" → 2023-04-15
- "2023-04-15T22:40:00" → exact timestamp

### Relative Dates (MEDIUM confidence)
- "the next day" → requires anchor date from context
- "two weeks later" → calculate from previous event

### Vague Dates (LOW confidence)
- "last summer" → flag for clarification
- "a while ago" → flag for clarification

### Date Sources
| Source | Confidence | Notes |
|--------|-----------|-------|
| Message timestamp | HIGH | From chat export metadata |
| Explicit in text | HIGH | "April 15, 2023" |
| Relative to previous | MEDIUM | "the next day" |
| Inferred from context | MEDIUM | "when we were at the hotel" |
| Vague | LOW | "last summer", "a while ago" |

## How to Build

### Step 1: Collect all events
```python
events = []
for segment in personal_legal_segments:
    extracted = extract_events(segment)  # Via cloud model
    events.extend(extracted)
```

### Step 2: Sort chronologically
```python
events.sort(key=lambda e: e["date"] or datetime.min)
```

### Step 3: Resolve ambiguities
- Group events by description similarity
- If same event from multiple sources, merge with all source refs
- Flag vague dates for human review

### Step 4: Export
```python
# Save to database
db.insert_timeline_events(events)

# Export for court
generate_timeline_pdf(events, output="timeline.pdf")
```

## Merging Events
When the same event appears in multiple conversations:
- Keep all verbatim quotes (each source may have different details)
- Merge people lists (deduplicate)
- Merge evidence refs (deduplicate)
- Use the HIGHEST confidence date
- Keep ALL source conversation references
