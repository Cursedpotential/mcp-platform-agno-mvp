import os
import shutil

# Create directories
os.makedirs("docs/reference", exist_ok=True)
os.makedirs("docs/cookbook", exist_ok=True)

# Modules to generate docs for
modules = {
    "core": "semantica.core",
    "ingest": "semantica.ingest",
    "parse": "semantica.parse",
    "normalize": "semantica.normalize",
    "semantic_extract": "semantica.semantic_extract",
    "kg": "semantica.kg",
    "embeddings": "semantica.embeddings",
    "vector_store": "semantica.vector_store",
    "triplet_store": "semantica.triplet_store",
    "ontology": "semantica.ontology",
    "reasoning": "semantica.reasoning",
    "pipeline": "semantica.pipeline",
    "export": "semantica.export",
    "visualization": "semantica.visualization",
    "utils": "semantica.utils"
}

# Generate reference markdown files
for name, package in modules.items():
    content = f"# {name.replace('_', ' ').title()}\n\n::: {package}\n"
    with open(f"docs/reference/{name}.md", "w") as f:
        f.write(content)
    print(f"Created docs/reference/{name}.md")

# Copy cookbook directory
if os.path.exists("cookbook"):
    if os.path.exists("docs/cookbook"):
        shutil.rmtree("docs/cookbook")
    shutil.copytree("cookbook", "docs/cookbook")
    print("Copied cookbook to docs/cookbook")

# Remove old files
files_to_remove = ["docs/MODULES_DOCUMENTATION.md", "docs/cookbook.md", "docs/api.md"]
for f in files_to_remove:
    if os.path.exists(f):
        os.remove(f)
        print(f"Removed {f}")
