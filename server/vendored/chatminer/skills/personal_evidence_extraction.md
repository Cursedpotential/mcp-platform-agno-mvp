# Skill: Personal Evidence Extraction

## Purpose
Extract entities, events, timelines, strategies, and artifacts from
personal/legal conversation segments.

## When to Use
- After topic segmentation identifies a `personal_legal` chunk
- Building the case timeline
- Identifying evidence to collect
- Documenting patterns of behavior

## What to Extract

### 1. People (Named Entities)
Look for: names, aliases, roles
- "Katrina Kinzel" → defendant
- "Matt Salem" → plaintiff (you)
- "[Attorney Name]" → legal counsel
- Witnesses, family members, third parties

### 2. Dates and Events
Look for: explicit dates, relative dates, time ranges
- "April 15, 2023" → explicit
- "the night of the incident" → relative (need context)
- "last summer" → vague (flag for clarification)

### 3. Locations
Look for: addresses, venues, cities, hotels
- "Hilton Garden Inn, Portland"
- "123 Main Street"
- GPS coordinates (from timeline analysis)

### 4. Evidence Artifacts
Look for: documents, photos, messages, recordings
- "the text from March 3rd"
- "the screenshot I took"
- "the hotel receipt"
- "the Facebook messages"

### 5. Patterns of Behavior
Look for: repeated actions, controlling behavior, abuse indicators
- "she would check my phone every night"
- "isolated me from my family"
- "threatened to take the kids"
- DARVO patterns (Deny, Attack, Reverse Victim and Offender)

### 6. Legal Strategies
Look for: theories, approaches, arguments
- "coercive control pattern"
- "timeline of isolation"
- "financial abuse evidence"
- "witness testimony plan"

### 7. Emotional Context
Look for: emotional state during events
- "I was terrified"
- "I felt trapped"
- "I didn't know what to do"
- Documents emotional impact for damages

## How to Use

Send `personal_legal` segments to Gemini with this prompt:

```
Analyze the following conversation segment for a legal case.
Extract:
1. Named people and their roles
2. Dates and events (chronological)
3. Locations mentioned
4. Evidence artifacts referenced
5. Patterns of behavior
6. Legal strategies discussed
7. Emotional context

Format as structured JSON with confidence scores (HIGH/MEDIUM/LOW).
Preserve all text VERBATIM — never summarize or paraphrase.

SEGMENT:
{segment_text}
```

## Confidence Levels
- **HIGH**: Explicit statement with clear context
- **MEDIUM**: Inferred from context, some ambiguity
- **LOW**: Speculative, needs verification
