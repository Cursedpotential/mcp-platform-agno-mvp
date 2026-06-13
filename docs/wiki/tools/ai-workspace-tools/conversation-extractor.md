# Conversation Extractor

## Overview
- **What**: Autopsy plugin for extracting and analyzing SMS conversations from Android device images
- **Version**: Latest
- **Category**: forensics | digital-evidence | autopsy-plugin
- **Framework**: Autopsy Plugin
- **Language**: Python

## Purpose
Extracts SMS conversations from Android device images and generates organized conversation transcripts for forensic analysis.

## Features
- Parses SMS conversations from mmssms.db file
- Groups messages by participants
- Orders messages by timestamp
- Generates conversation transcripts
- Integrates with Autopsy reporting

## Installation
```bash
# 1. Download source code
# 2. Place in Autopsy python_modules folder
# 3. Open Autopsy and navigate to Generate Report
# 4. Select "Conversation Identifier & Extractor" report
# 5. Run report to generate conversation transcript
```

## How It Works
1. **Parse Database**: Reads mmssms.db from Android device image
2. **Extract Messages**: Extracts all SMS messages with metadata
3. **Group Conversations**: Groups messages by common participants
4. **Order by Timestamp**: Sorts messages chronologically
5. **Generate Report**: Creates conversation transcript in Autopsy report

## Use Cases
- Digital forensics analysis
- Android device examination
- SMS conversation recovery
- Evidence collection
- Timeline reconstruction
- Conversation analysis

## Output
- Organized conversation transcripts
- Participant identification
- Timestamp information
- Message content
- Autopsy report integration

## Requirements
- Autopsy installed
- Python support enabled in Autopsy
- Android device image

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
**Autopsy**: https://www.sleuthkit.org/autopsy/
