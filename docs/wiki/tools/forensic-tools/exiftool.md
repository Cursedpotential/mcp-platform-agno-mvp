# ExifTool 12.69

## Overview
- **What**: Command-line tool for reading and writing metadata in 100+ file types
- **Version**: 12.69
- **Category**: forensics | metadata-extraction | digital-evidence
- **Language**: Perl

## Purpose
Comprehensive metadata extraction and manipulation tool for digital forensics and evidence analysis.

## Supported File Types (100+)
**Images**: JPEG, PNG, TIFF, GIF, BMP, WEBP, HEIC, RAW formats
**Videos**: MP4, MOV, AVI, MKV, WebM, FLV
**Documents**: PDF, DOCX, XLSX, PPTX, ODT, ODS
**Audio**: MP3, WAV, FLAC, AAC, OGG
**Archives**: ZIP, RAR, 7Z
**And many more...**

## Metadata Types
- EXIF (camera settings, GPS, timestamps)
- GPS coordinates and altitude
- IPTC (keywords, copyright, description)
- XMP (extensible metadata)
- MakerNotes (camera-specific data)
- ICC Profiles
- PDF metadata

## Installation
```bash
cd D:/Users/matts/Downloads/_Software_Installers/Image-ExifTool-12.69
perl Makefile.PL
make
make test
make install
```

## Usage Examples
```bash
# Extract all metadata
exiftool image.jpg

# Extract GPS data
exiftool -GPS* image.jpg

# Extract EXIF data
exiftool -EXIF:* image.jpg

# Batch extract from directory
exiftool -r /path/to/directory

# Write metadata
exiftool -Copyright="My Copyright" image.jpg

# Remove metadata
exiftool -All= image.jpg
```

## Use Cases
- Digital forensics analysis
- Metadata extraction from evidence
- Chain of custody documentation
- Batch metadata processing
- Geolocation analysis from photos
- Timestamp verification

## Key Features
- Read/write metadata in 100+ formats
- Batch processing capabilities
- Customizable output formats
- Perl module API for scripting
- No external dependencies required

---
**Last Updated**: 2026-03-15
**Status**: Production Ready
**Official Site**: https://exiftool.org/
