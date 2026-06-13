# Installation

Get Semantica up and running in minutes.

!!! success "Now Available on PyPI!"
    Semantica is officially published on PyPI! Install it with a single command: `pip install semantica`

!!! note "System Requirements"
    Semantica requires Python 3.8 or higher. For best performance, we recommend Python 3.10+.

## Prerequisites

Before installing Semantica, ensure you have:

- **Python 3.8 or higher** - Check your version:
  ```bash
  python --version
  ```
- **pip** - Python package installer (usually comes with Python)

## Basic Installation

Install Semantica from PyPI:

```bash
pip install semantica
```

This installs Semantica with all core dependencies.

### GitHub Workaround

If you encounter issues with the PyPI version, you can install directly from the main branch:

```bash
pip install git+https://github.com/Hawksight-AI/semantica.git@main
```

!!! tip "Virtual Environment"
    We recommend installing Semantica in a virtual environment to avoid dependency conflicts. Use `python -m venv venv` to create one, then activate it before installing.

## Verify Installation

Verify that Semantica is installed correctly:

```bash
python -c "from semantica.parse import DoclingParser; DoclingParser(); print('✓ Semantica ready')"
```

!!! info "Windows PyTorch Note"
    If you encounter PyTorch DLL errors on Windows, ensure you have the [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) installed. This is a common environment-specific issue with PyTorch on Windows and not a bug in Semantica.

Expected output:
```
✓ Semantica ready
```

You can also check the installation:

```bash
pip show semantica
```

## Development Installation

To install Semantica in development mode (for contributing):

```bash
# Clone the repository
git clone https://github.com/Hawksight-AI/semantica.git
cd semantica

# Install in editable mode
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Optional Dependencies

Semantica supports optional features that can be installed separately:

### GPU Support

For GPU-accelerated operations:

```bash
pip install semantica[gpu]
```

This includes:
- PyTorch with CUDA support
- FAISS GPU
- CuPy

### Visualization

For enhanced visualization capabilities:

```bash
pip install semantica[viz]
```

Includes:
- PyVis for interactive graphs
- Graphviz for static diagrams
- UMAP for dimensionality reduction

### LLM Providers

Install all LLM provider integrations:

```bash
pip install semantica[llm-all]
```

Or install specific providers:

```bash
# OpenAI
pip install semantica[llm-openai]

# Anthropic
pip install semantica[llm-anthropic]

# Google Gemini
pip install semantica[llm-gemini]

# Groq
pip install semantica[llm-groq]

# Ollama
pip install semantica[llm-ollama]
```

### Cloud Integrations

For cloud storage and deployment:

```bash
pip install semantica[cloud]
```

Includes:
- AWS S3 (boto3)
- Azure Blob Storage
- Google Cloud Storage
- Kubernetes support

### All Optional Features

Install everything:

```bash
pip install semantica[all]
```

## Virtual Environment (Recommended)

It's recommended to use a virtual environment:

=== "venv"

    ```bash
    # Create virtual environment
    python -m venv venv

    # Activate (Windows)
    venv\Scripts\activate

    # Activate (Linux/Mac)
    source venv/bin/activate

    # Install Semantica
    pip install semantica
    ```

=== "conda"

    ```bash
    # Create conda environment
    conda create -n semantica python=3.11
    conda activate semantica

    # Install Semantica
    pip install semantica
    ```

## Troubleshooting

### Common Issues

#### ModuleNotFoundError

**Error**: `ModuleNotFoundError: No module named 'semantica'`

**Solutions**:
- Make sure you've activated the correct Python environment
- Verify installation: `pip list | grep semantica`
- Reinstall: `pip install --upgrade semantica`

#### Installation Fails

**Error**: Installation fails with dependency errors

**Solutions**:
- Upgrade pip: `pip install --upgrade pip`
- Install build tools: `pip install build wheel`
- Try installing without optional dependencies first: `pip install semantica --no-deps`

#### GPU Dependencies Fail

**Error**: GPU dependencies fail to install

**Solutions**:
- Install CPU-only version first: `pip install semantica`
- Then add GPU support: `pip install semantica[gpu]`
- Check CUDA compatibility for your system

#### Permission Errors

**Error**: Permission denied during installation

**Solutions**:
- Use `--user` flag: `pip install --user semantica`
- Use virtual environment (recommended)
- On Linux/Mac, avoid using `sudo` with pip

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.8 | 3.11+ |
| RAM | Moderate | Ample for your dataset |
| Disk Space | Sufficient for data | Generous storage |
| OS | Windows/Linux/Mac | Linux/Mac |

## After Installation

Once Semantica is installed, verify your setup and get started:

### Verify Your Installation

Test that everything works correctly:

```bash
python -c "import semantica; print(semantica.__version__)"
```

**For detailed setup verification and first steps, see:**
- **[Welcome to Semantica Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)**: Verify installation and explore all modules
  - **Topics**: Framework overview, installation verification, module exploration
  - **Difficulty**: Beginner
  - **Time**: 30-45 minutes
  - **Use Cases**: First-time setup, understanding the framework

## Next Steps

Now that Semantica is installed:

1. **[Quick Start Guide](quickstart.md)** - Build your first knowledge graph in 5 minutes
2. **[Getting Started Guide](getting-started.md)** - Learn the fundamentals
3. **[Examples](examples.md)** - See real-world use cases
4. **[Cookbook](cookbook.md)** - Interactive Jupyter notebook tutorials

### 🍳 Recommended First Cookbooks

Start with these interactive tutorials:

- **[Welcome to Semantica](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)**: Comprehensive introduction
  - **Topics**: Framework overview, all modules, architecture, configuration
  - **Difficulty**: Beginner
  - **Time**: 30-45 minutes
  - **Use Cases**: First-time users, understanding the framework

- **[Your First Knowledge Graph](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/08_Your_First_Knowledge_Graph.ipynb)**: Build your first graph
  - **Topics**: Entity extraction, relationship extraction, graph construction
  - **Difficulty**: Beginner
  - **Time**: 20-30 minutes
  - **Use Cases**: Hands-on practice, quick start

## Getting Help

If you encounter issues:

- Check the [troubleshooting section](#troubleshooting) above
- Review [GitHub Issues](https://github.com/Hawksight-AI/semantica/issues)
- Ask questions in [GitHub Discussions](https://github.com/Hawksight-AI/semantica/discussions)

**For installation and setup help:**
- **[Welcome to Semantica Cookbook](https://github.com/Hawksight-AI/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb)**: Includes setup verification steps
- **[Installation Troubleshooting Guide](getting-started.md#installation--setup)**: Additional troubleshooting tips
