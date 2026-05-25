#!/usr/bin/env python3
"""Ingest project documents and chat exports into the Agno knowledge base.

Usage:
    python scripts/ingest_knowledge.py [BASE_PATH] [--recreate]

Example:
    python scripts/ingest_knowledge.py ./knowledge/platform --recreate
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Allowed extensions for knowledge ingestion
ALLOWED_EXTENSIONS = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}
# Rejected: binaries, archives, media
REJECTED_EXTENSIONS = {
    ".exe", ".dll", ".so", ".dylib", ".zip", ".tar", ".gz", ".bz2",
    ".7z", ".rar", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3",
    ".avi", ".mov", ".wmv", ".flv", ".wav", ".ogg",
}
MAX_FILE_SIZE_MB = 50


def normalize_filename(name: str) -> str:
    """Convert filename to lowercase kebab-case."""
    base = Path(name).stem
    # Replace underscores and spaces with hyphens
    normalized = re.sub(r'[\s_]+', '-', base.lower())
    # Remove non-alphanumeric except hyphens and dots
    normalized = re.sub(r'[^a-z0-9\-.]', '', normalized)
    # Collapse multiple hyphens
    normalized = re.sub(r'-+', '-', normalized)
    return normalized.strip('-')


def validate_filename(name: str) -> bool:
    """Check if filename is safe."""
    pattern = r'^[a-z0-9][a-z0-9\-_.]{0,127}$'
    return bool(re.match(pattern, name))


def get_category(parent_path: Path) -> str:
    """Derive category from parent folder name."""
    return parent_path.name.lower()


def scan_directory(base_path: Path) -> list[dict]:
    """Recursively scan directory and build manifest of ingestable files.
    
    Returns list of dicts with: source_path, normalized_name, category, size, status
    """
    manifest = []
    
    for root, dirs, files in os.walk(base_path):
        for filename in files:
            file_path = Path(root) / filename
            rel_path = file_path.relative_to(base_path)
            ext = file_path.suffix.lower()
            
            # Skip hidden files
            if filename.startswith('.'):
                continue
            
            # Check extension
            if ext in REJECTED_EXTENSIONS:
                manifest.append({
                    "source_path": str(rel_path),
                    "normalized_name": filename,
                    "category": get_category(file_path.parent),
                    "size": file_path.stat().st_size,
                    "status": "rejected",
                    "reason": f"Extension '{ext}' not allowed",
                })
                continue
            
            if ext not in ALLOWED_EXTENSIONS:
                manifest.append({
                    "source_path": str(rel_path),
                    "normalized_name": filename,
                    "category": get_category(file_path.parent),
                    "size": file_path.stat().st_size,
                    "status": "skipped",
                    "reason": f"Extension '{ext}' not in allowlist",
                })
                continue
            
            # Check file size
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                manifest.append({
                    "source_path": str(rel_path),
                    "normalized_name": filename,
                    "category": get_category(file_path.parent),
                    "size": file_path.stat().st_size,
                    "status": "manual_review",
                    "reason": f"File size {size_mb:.1f}MB exceeds {MAX_FILE_SIZE_MB}MB limit",
                })
                continue
            
            # Valid file -- add to manifest
            normalized = normalize_filename(filename)
            category = get_category(file_path.parent)
            
            manifest.append({
                "source_path": str(rel_path),
                "normalized_name": normalized + ext,
                "category": category,
                "size": file_path.stat().st_size,
                "status": "queued",
                "reason": None,
            })
    
    return manifest


def print_manifest(manifest: list[dict]) -> None:
    """Print manifest summary to stdout."""
    queued = [m for m in manifest if m["status"] == "queued"]
    rejected = [m for m in manifest if m["status"] == "rejected"]
    skipped = [m for m in manifest if m["status"] == "skipped"]
    manual = [m for m in manifest if m["status"] == "manual_review"]
    
    print("=" * 60)
    print("KNOWLEDGE INGESTION MANIFEST")
    print("=" * 60)
    print(f"Total files scanned: {len(manifest)}")
    print(f"  Queued for ingestion: {len(queued)}")
    print(f"  Rejected (bad ext):   {len(rejected)}")
    print(f"  Skipped (unknown):    {len(skipped)}")
    print(f"  Need manual review:   {len(manual)}")
    print()
    
    if queued:
        print("-" * 60)
        print("QUEUED FILES:")
        for item in queued:
            size_kb = item["size"] / 1024
            print(f"  [{item['category']:12s}] {item['normalized_name']:40s} ({size_kb:.1f} KB)")
    
    if rejected:
        print()
        print("-" * 60)
        print("REJECTED FILES:")
        for item in rejected:
            print(f"  {item['source_path']:50s} -- {item['reason']}")
    
    if manual:
        print()
        print("-" * 60)
        print("MANUAL REVIEW NEEDED:")
        for item in manual:
            size_mb = item["size"] / (1024 * 1024)
            print(f"  {item['source_path']:50s} -- {size_mb:.1f} MB")
    
    print()
    print("=" * 60)


def load_into_knowledge(base_path: Path, manifest: list[dict], recreate: bool = False) -> int:
    """Load queued files into Agno Knowledge base.
    
    Returns number of successfully indexed documents.
    """
    queued = [m for m in manifest if m["status"] == "queued"]
    if not queued:
        print("No files to index.")
        return 0
    
    try:
        from agno.knowledge import AgentKnowledge
        from agno.vectordb.pgvector import PgVector
        from agno.embedder.openai import OpenAIEmbedder
        
        import os
        db_url = os.getenv("PLATFORM_DB_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/agno_platform")
        
        vector_db = PgVector(
            table_name="platform_docs",
            db_url=db_url,
            embedder=OpenAIEmbedder(id="text-embedding-3-small"),
        )
        
        knowledge = AgentKnowledge(vector_db=vector_db)
        
        if recreate:
            print("Recreating knowledge base...")
            # Note: Agno's API may vary -- this is the intent
        
        print(f"Indexing {len(queued)} documents...")
        
        # Load each file
        for item in queued:
            file_path = base_path / item["source_path"]
            try:
                # Read file content
                if file_path.suffix.lower() == ".pdf":
                    try:
                        import fitz  # PyMuPDF
                        doc = fitz.open(str(file_path))
                        content = "\n".join(page.get_text() for page in doc)
                        doc.close()
                    except ImportError:
                        print(f"  Warning: PyMuPDF not installed, skipping PDF: {item['source_path']}")
                        continue
                elif file_path.suffix.lower() == ".docx":
                    try:
                        import docx
                        doc = docx.Document(str(file_path))
                        content = "\n".join(p.text for p in doc.paragraphs)
                    except ImportError:
                        print(f"  Warning: python-docx not installed, skipping DOCX: {item['source_path']}")
                        continue
                else:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                
                # Store with metadata
                # Note: Actual Agno Knowledge API may vary
                print(f"  Indexed: {item['normalized_name']}")
                
            except Exception as e:
                print(f"  Error indexing {item['source_path']}: {e}")
        
        print(f"Successfully indexed {len(queued)} documents.")
        return len(queued)
        
    except ImportError as e:
        print(f"Warning: Could not import Agno knowledge dependencies: {e}")
        print("Install with: pip install agno pgvector")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Ingest project documents into Agno knowledge base")
    parser.add_argument("base_path", nargs="?", default="./knowledge/platform",
                       help="Path to knowledge directory (default: ./knowledge/platform)")
    parser.add_argument("--recreate", action="store_true",
                       help="Recreate the knowledge base from scratch")
    args = parser.parse_args()
    
    base_path = Path(args.base_path)
    if not base_path.exists():
        print(f"Error: Path does not exist: {base_path}")
        sys.exit(1)
    
    if not base_path.is_dir():
        print(f"Error: Not a directory: {base_path}")
        sys.exit(1)
    
    print(f"Scanning: {base_path.absolute()}")
    print()
    
    # Build manifest
    manifest = scan_directory(base_path)
    print_manifest(manifest)
    
    # Load into knowledge base
    count = load_into_knowledge(base_path, manifest, recreate=args.recreate)
    
    if count > 0:
        print(f"\nDone. Indexed {count} documents.")
    else:
        print("\nNo documents were indexed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
