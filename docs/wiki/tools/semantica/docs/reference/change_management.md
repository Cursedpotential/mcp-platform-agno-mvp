# Change Management

**Enterprise-grade version control and audit trails for knowledge graphs and ontologies with data integrity verification**

## Overview

The Semantica change management module provides enterprise-grade version control, audit trails, and compliance tracking for knowledge graphs and ontologies. Designed for high-stakes domains where every change must be tracked, verified, and auditable with complete data integrity guarantees.

<div class="grid cards" markdown>

-   :material-history:{ .lg .middle } **Version Control**

    ---

    Complete snapshot management with SHA-256 integrity verification

-   :material-database:{ .lg .middle } **Dual Storage**

    ---

    InMemory (development) and SQLite (production) with ACID guarantees

-   :material-graph:{ .lg .middle } **Knowledge Graph Versioning**

    ---

    Entity and relationship-level change tracking with detailed diffs

-   :material-shape:{ .lg .middle } **Ontology Versioning**

    ---

    Structural change tracking for classes, properties, and axioms

-   :material-clipboard-check:{ .lg .middle } **Audit Trail Compliance**

    ---

    Complete change logs with author attribution and timestamps

-   :material-shield-check:{ .lg .middle } **Data Integrity**

    ---

    SHA-256 checksums for tamper detection and verification

-   :material-compare:{ .lg .middle } **Change Comparison**

    ---

    Detailed diff algorithms for entities, relationships, and ontology structures

-   :material-backup-restore:{ .lg .middle } **Backward Compatibility**

    ---

    Legacy support for existing ontology version management

</div>

### Key Features

- ✅ **Enterprise Version Control** — Complete snapshot management with SHA-256 integrity verification
- ✅ **Dual Storage Backends** — InMemory (development) and SQLite (production) with ACID guarantees
- ✅ **Knowledge Graph Versioning** — Entity and relationship-level change tracking with detailed diffs
- ✅ **Ontology Versioning** — Structural change tracking for classes, properties, and axioms
- ✅ **Audit Trail Compliance** — Complete change logs with author attribution and timestamps
- ✅ **Data Integrity** — SHA-256 checksums for tamper detection and verification
- ✅ **Change Comparison** — Detailed diff algorithms for entities, relationships, and ontology structures
- ✅ **Backward Compatibility** — Legacy support for existing ontology version management

---

## Quick Start

```python
from semantica.change_management import TemporalVersionManager

# Initialize version manager
manager = TemporalVersionManager(storage_path="versions.db")

# Create versioned snapshot
snapshot = manager.create_snapshot(
    graph={"entities": [...], "relationships": [...]},
    version_label="v1.0",
    author="user@example.com",
    description="Initial knowledge graph"
)

# Compare versions
diff = manager.compare_versions("v1.0", "v2.0")
```

**What this does:**
- Initializes version manager with persistent SQLite storage
- Creates a versioned snapshot of knowledge graph data
- Compares two versions to detect changes
- Provides complete audit trail with author attribution

---

## Core Components

### ChangeLogEntry

Standardized metadata for tracking version changes with validation.

```python
from semantica.change_management import ChangeLogEntry

@dataclass
class ChangeLogEntry:
    timestamp: str          # ISO 8601 format
    author: str             # Email address
    description: str        # Max 500 characters
    change_id: Optional[str] = None
```

**Key Method:**
- `create_now(author, description, change_id=None)` - Create entry with current timestamp

### Storage Backends

#### InMemoryVersionStorage
Fast, volatile storage for development and testing.
```python
from semantica.change_management import InMemoryVersionStorage

storage = InMemoryVersionStorage()
```

#### SQLiteVersionStorage
Persistent storage with ACID guarantees for production.
```python
from semantica.change_management import SQLiteVersionStorage

storage = SQLiteVersionStorage("versions.db")
```

#### VersionStorage (Abstract)
Base interface for custom storage implementations.

**Core Methods:**
- `save(snapshot)` - Store version snapshot
- `get(label)` - Retrieve by version label
- `list_all()` - List all versions
- `exists(label)` - Check if version exists
- `delete(label)` - Remove version

---

## Version Managers

### BaseVersionManager

Abstract base class providing common version management functionality.

```python
from semantica.change_management import BaseVersionManager

manager = BaseVersionManager(storage_path="versions.db")
```

**Common Methods:**
- `list_versions()` - Get all version metadata
- `get_version(label)` - Retrieve specific version
- `verify_checksum(snapshot)` - Validate data integrity

### TemporalVersionManager

**Knowledge Graph Version Management**

Perfect for tracking changes in knowledge graphs with entity and relationship diffs.

```python
from semantica.change_management import TemporalVersionManager

manager = TemporalVersionManager(storage_path="kg_versions.db")

# Create snapshot
snapshot = manager.create_snapshot(
    graph={
        "entities": [
            {"id": "e1", "name": "Entity 1", "type": "Person"},
            {"id": "e2", "name": "Entity 2", "type": "Organization"}
        ],
        "relationships": [
            {"source": "e1", "target": "e2", "type": "works_for"}
        ]
    },
    version_label="v1.0",
    author="user@example.com",
    description="Initial knowledge graph"
)

# Compare versions with detailed diffs
diff = manager.compare_versions("v1.0", "v2.0")
print(f"Entities added: {diff['summary']['entities_added']}")
print(f"Relationships modified: {diff['summary']['relationships_modified']}")
```

**Key Features:**
- Entity-level change tracking
- Relationship diff analysis
- SHA-256 checksums for integrity
- Detailed change summaries

### OntologyVersionManager

**Ontology Version Management**

Designed for structural changes in ontologies with class, property, and axiom tracking.

```python
from semantica.change_management import OntologyVersionManager

manager = OntologyVersionManager(storage_path="ontology_versions.db")

# Create ontology snapshot
snapshot = manager.create_snapshot(
    ontology={
        "uri": "https://example.com/ontology",
        "structure": {
            "classes": ["Person", "Organization"],
            "properties": ["name", "email"],
            "axioms": ["Person hasEmail exactly 1 Email"]
        }
    },
    version_label="ont_v1.0",
    author="architect@example.com",
    description="Initial ontology design"
)

# Compare structural changes
diff = manager.compare_versions("ont_v1.0", "ont_v2.0")
print(f"Classes added: {diff['classes_added']}")
print(f"Axioms modified: {diff['axioms_modified']}")
```

**Key Features:**
- Class and property tracking
- Axiom change detection
- Structural comparison
- Import/export support

---

## Data Integrity

### compute_checksum

Generate SHA-256 checksum for data integrity verification.

```python
from semantica.change_management import compute_checksum

data = {"entities": [...], "relationships": [...]}
checksum = compute_checksum(data)
print(f"SHA-256: {checksum}")
```

**Use cases:**
- Verify data integrity before storing snapshots
- Detect unauthorized modifications to version data
- Ensure consistency across distributed systems
- Generate unique identifiers for data versions

### verify_checksum

Validate data integrity using stored checksums.

```python
from semantica.change_management import verify_checksum

snapshot = manager.get_version("v1.0")
is_valid = verify_checksum(snapshot)

if not is_valid:
    print("WARNING: Data integrity compromised!")
```

**Use cases:**
- Validate snapshot integrity after retrieval
- Detect data corruption or tampering
- Ensure compliance with data integrity requirements
- Verify backup and restore operations

---

## Legacy Support

### VersionManager

Original ontology version manager for backward compatibility.

```python
from semantica.change_management import VersionManager, OntologyVersion
```

**Note:** Use `OntologyVersionManager` for new projects.

---

## Error Handling

```python
from semantica.utils.exceptions import ValidationError, ProcessingError

try:
    snapshot = manager.create_snapshot(...)
except ValidationError as e:
    print(f"Invalid input: {e}")
except ProcessingError as e:
    print(f"Operation failed: {e}")
```

**Common Errors:**
- `ValidationError` - Invalid email, missing fields, bad timestamps
- `ProcessingError` - Database issues, file system errors

---

## Best Practices

### Performance Tips
- Use `InMemoryVersionStorage` for development/testing
- Use `SQLiteVersionStorage` for production
- Implement retention policies for old versions

### Security Considerations
- Validate author emails for audit trails
- Use checksums for data integrity
- Store sensitive data with appropriate permissions

### Usage Patterns
```python
from semantica.change_management import TemporalVersionManager

# Development workflow
dev_manager = TemporalVersionManager()  # In-memory

# Production workflow  
prod_manager = TemporalVersionManager(
    storage_path="secure/production_versions.db"
)

# Audit trail generation
for version in prod_manager.list_versions():
    print(f"{version['timestamp']}: {version['description']} by {version['author']}")
```
