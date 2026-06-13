# Analyze Triggers - Skill Reference

## Overview
- **What**: Scans Claude skill triggers for anti-patterns and quality issues
- **Version**: 1.0.0
- **Category**: analysis | quality-assurance | nlp
- **Installed In**: `utilities/scripts/analyze_triggers.py`
- **Status**: Active (skill quality monitoring)

## Purpose

Analyze Triggers enables skill quality assurance:
1. **Scan triggers** for anti-patterns
2. **Detect introspection** - vague emotional language
3. **Find emotional words** - overwhelmed, stuck, confused
4. **Report issues** - actionable quality feedback
5. **Support improvement** - guide skill refinement

## Anti-Patterns Detected

**Introspection verbs**: notice, catch, sense, realize
- Problem: Too vague, hard to trigger reliably
- Solution: Use specific, observable conditions

**Emotional words**: overwhelmed, stuck, confused, frustrated
- Problem: Subjective, hard to detect
- Solution: Use behavioral indicators instead

## When to Use It

### Primary Use Cases
- **Skill review**: Audit trigger quality
- **Marketplace prep**: Prepare skills for publication
- **Quality gates**: Enforce trigger standards
- **Training**: Teach trigger best practices
- **Monitoring**: Track skill quality over time

## Dependencies

### Required
- **Python 3.6+**
- **pathlib** (stdlib)
- **collections** (stdlib)

## Usage Examples

### Basic Usage
```bash
python analyze_triggers.py
```

## Online Repo & Docs

- **GitHub**: https://github.com/Cursedpotential/mcp-tool-platform/tree/main/utilities/scripts

---

**Last Updated**: 2026-03-15
**Status**: Production-ready
