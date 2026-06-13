# Pandoc Converter - Skill Reference

## Overview
- **What**: Universal document converter using Pandoc (MD, DOCX, HTML to PDF and vice versa)
- **Version**: 1.0.0
- **Category**: converter | document-processing
- **Installed In**: `utilities/scripts/pandoc_converter.py`
- **Status**: Active (multi-format document conversion)

## Purpose

Pandoc Converter enables universal document conversion:
1. **Convert formats** - MD, DOCX, HTML, TXT to PDF and vice versa
2. **Batch process** - convert entire directories
3. **Auto-detect engines** - finds available PDF engines
4. **Format documents** - applies consistent styling
5. **Report progress** - shows success/failure counts

## When to Use It

### Primary Use Cases
- **Batch conversion**: Convert entire document folders
- **Format standardization**: Convert all docs to PDF
- **Report generation**: Convert markdown reports to PDF
- **Archive preparation**: Convert to standard formats
- **Distribution**: Create PDF versions for sharing

## Dependencies

### Required
- **Python 3.6+**
- **pandoc** - Document converter

### Optional (for PDF output)
- **wkhtmltopdf** - Best for HTML/MD
- **pdflatex** - LaTeX-based
- **weasyprint** - Python-based

## Usage Examples

### Basic Usage
```bash
python pandoc_converter.py ./markdown_folder
python pandoc_converter.py ./markdown_folder --format pdf
python pandoc_converter.py ./docx_folder --format pdf
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts
- **Pandoc**: https://pandoc.org/

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
