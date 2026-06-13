# Batch Processing

Process multiple chat transcripts and merge context. Optimized for Claude Haiku.

## System Prompt

```
You process multiple chat transcripts and merge extracted context.

Workflow:
1. Process each transcript file
2. Extract context from each
3. Merge into unified context
4. Resolve conflicts (prefer recent, specific over old, vague)
5. Output merged context OR chunked files

Rules for merging:
- Later information overrides earlier (things change)
- More specific overrides general
- Keep all unique details
- Note contradictions with [updated] or [previously]
- Combine project lists, don't replace

Conflict example:
- Transcript 1: "I work at Company A"
- Transcript 2: "Starting new job at Company B next week"
Result: "Works at Company B [previously Company A]"

Output options:
1. Single merged context document
2. Individual themed chunk files
3. Both
```

## Batch Workflow

### Option A: Sequential (for Haiku)

Process one transcript at a time, accumulate context:

```
1. Process transcript_1.json → context_1.md
2. Process transcript_2.json → context_2.md  
3. Process transcript_3.json → context_3.md
4. Merge: context_1 + context_2 + context_3 → merged_context.md
5. Chunk: merged_context.md → themed files
```

### Option B: Parallel (for larger models)

Process all at once:

```
1. Load all transcripts
2. Extract context from all simultaneously
3. Merge and chunk in single pass
```

### Option C: Incremental

Update existing context with new transcripts:

```
1. Load existing chunked files
2. Process new transcript
3. Merge new context into existing files
4. Flag updates and changes
```

## Directory Structure

```
context-project/
├── raw/                    # Original exports
│   ├── claude-export-1.json
│   ├── claude-export-2.json
│   └── chatgpt-export.json
├── processed/              # Clean transcripts
│   ├── transcript-1.txt
│   ├── transcript-2.txt
│   └── transcript-3.txt
├── extracted/              # Raw extracted context
│   ├── context-1.md
│   ├── context-2.md
│   └── context-3.md
├── merged/                 # Combined context
│   └── full-context.md
└── chunks/                 # Final themed files
    ├── personal-background.md
    ├── work-context.md
    ├── technical-stack.md
    └── current-projects.md
```

## Merge Prompt (Haiku-optimized)

```
Merge these context extracts into one document.

Rules:
1. Combine all unique information
2. Recent info overrides old
3. Note major changes with [updated]
4. Remove exact duplicates
5. Keep all project names and details

Input contexts:
[paste extracted contexts]

Output: Single merged context document with all categories.
```

## Incremental Update Prompt

```
Update existing context with new information.

Existing context:
[paste current context]

New information:
[paste new extraction]

Rules:
1. Add new facts
2. Update changed facts (mark with [updated])
3. Keep unchanged facts as-is
4. Note removed/contradicted info

Output: Updated context document.
```
