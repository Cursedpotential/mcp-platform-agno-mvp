# Code Annotations - dial-stack

*Exported on 3/16/2026, 3:34:12 PM*

## .plannotator/drafts/development-bible-agent-governance-2026-03-16.md

### [Open] Annotation 1

**Author:** matts  
**Date:** 3/16/2026, 3:27:36 PM  
**Lines:** 65-65  
**Status:** Open

**Code:**
```
**TS MCP Server — 1,717 lines across 8 files:**
```

**Comment:**
We had also decided on using IBM's MCP gateway proxy platform which also handles Apis and RPCS it's kind of an all in one It also will handle off it also handles entity identification it also handles abusive language detection so we might be able to really utilize the shit out of that whether or not it becomes a primary tool or a pre scan tool kind of depends on how well it integrates with our existing identification features and tools and and ontologies and stuff and such but we need to get a good grip on that and how it will work together with Dial we might only be using dial for the front end authentication and use IBM for all of the back end stuff API MCP all that

---

### [Open] Annotation 2

**Author:** matts  
**Date:** 3/16/2026, 3:28:06 PM  
**Lines:** 48-48  
**Status:** Open

**Code:**
```
**Key Architectural Principles (from memory files + plannotator history):**
```

**Comment:**
There's also a shit ton more tools in the Utilities folder as well as the legacy folders in DAI Workspace and the sister folder MCP Tool Platform as well as my Downloads directory

---

### [Open] Annotation 3

**Author:** matts  
**Date:** 3/16/2026, 3:29:37 PM  
**Lines:** 89-90  
**Status:** Open

**Code:**
```
**Client:** Scaffolded React + CopilotKit. Default Vite template counter button. No custom UI.

```

**Comment:**
I never said anything about no custom UI The React front end is all custom there's a bunch of code in the legacy directory a bunch of it also there's a couple of frameworks that I was looking at that would play nice with the other applications I just need to know what all is included with Copilot Kit and dial as far as framework like UI components and modules but there's a couple of frameworks I was looking at for modular react things

---

### [Open] Annotation 4

**Author:** matts  
**Date:** 3/16/2026, 3:30:20 PM  
**Lines:** 102-103  
**Status:** Open

**Code:**
```
8. **Semantica tool implementations** — server.py registers 30+ tools but actual semantica_tools.py, lancedb_tools.py, neo4j_tools.py files don't exist in py-mcp-server/src/tools/

```

**Comment:**
This is avip this is kind of the centerpiece of the entire application so even if it's not an MVP it it's definitely next it needs to be very functional very soon

---

### [Open] Annotation 5

**Author:** matts  
**Date:** 3/16/2026, 3:30:38 PM  
**Lines:** 111-112  
**Status:** Open

**Code:**
```
- MCP ports exposed → Fixed: internal-only (Remediation #1)

```

**Comment:**
See comment about the IBM tool implementation

---

### [Open] Annotation 6

**Author:** matts  
**Date:** 3/16/2026, 3:31:29 PM  
**Lines:** 155-156  
**Status:** Open

**Code:**
```
Every agent session starts by reading CLAUDE.md, then the relevant spec. No assumptions about what's built, what works, or what's been decided. If it's not in the docs, confirm with the user.

```

**Comment:**
yes

---

### [Open] Annotation 7

**Author:** matts  
**Date:** 3/16/2026, 3:31:53 PM  
**Lines:** 157-158  
**Status:** Open

**Code:**
```
**RULE 2: CONFIRM BEFORE CREATING**

```

**Comment:**
yes

---

### [Open] Annotation 8

**Author:** matts  
**Date:** 3/16/2026, 3:32:05 PM  
**Lines:** 160-160  
**Status:** Open

**Code:**
```
**
```

**Comment:**
yes

---

### [Open] Annotation 9

**Author:** matts  
**Date:** 3/16/2026, 3:32:15 PM  
**Lines:** 163-164  
**Status:** Open

**Code:**
```
**RULE 4: READ-ONLY LEGACY**

```

**Comment:**
yes

---

### [Open] Annotation 10

**Author:** matts  
**Date:** 3/16/2026, 3:32:43 PM  
**Lines:** 166-166  
**Status:** Open

**Code:**
```
**RULE 5: NO SILENT DECISIONS**
```

**Comment:**
yes. And we're going to split concerns and tasks across multiple agents and people need to stay in their lane when doing so

---

### [Open] Annotation 11

**Author:** matts  
**Date:** 3/16/2026, 3:32:52 PM  
**Lines:** 166-166  
**Status:** Open

**Code:**
```
**RULE 5: NO SILENT DECISIONS**
```

**Comment:**
Otherwise approved

---

### [Open] Annotation 12

**Author:** matts  
**Date:** 3/16/2026, 3:34:00 PM  
**Lines:** 216-217  
**Status:** Open

**Code:**
```
1. **Is this description of the app accurate?** If not, what's wrong?

```

**Comment:**
Everything here is approved I would like you to quickly have an agent a cheap one scan the planetator folder that I just copied in Unless you already read all of these these are the ones that was in my user directory i've moved it to the project directory If you read all of these good if you did not then you need to just for context but you need to have a cheap agent because I'm almost out of money man

---

