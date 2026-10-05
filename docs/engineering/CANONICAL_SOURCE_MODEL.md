# Canonical Source Model

Phase 1 defines the common provenance-preserving representation for every future ingestion adapter. It does not parse WhatsApp, call Docling/OCR/ASR, connect to MongoDB, or change inference behavior.

The implementation is in `app/source/models.py` and is re-exported by `app/source/__init__.py`.

## Source-level model

`CanonicalSource` contains:

- `source_id`: generated stable identifier, independent of list position.
- `source_type`: `whatsapp`, `pdf`, `docx`, `pptx`, `image`, `audio`, or `unknown`.
- `original_filename`, `mime_type`, `file_size_bytes`, and `original_metadata`.
- `ingested_at` as a timezone-aware timestamp.
- `processing_status`: `pending`, `processing`, `completed`, `partial`, or `failed`.
- `warnings` and `errors`, which preserve partial-success diagnostics.
- `units`, the ordered normalized content units.
- `extraction`, which records method/tool/status and extraction diagnostics.
- Optional `workspace_id` for future persistence and isolation.

## Content units

`ContentUnit` is intentionally source-neutral. Its `content_type` supports messages, paragraphs, headings, tables, OCR blocks, transcript segments, and an extensible `other` value. Each unit contains a generated `unit_id`, owning `source_id`, text, zero-based `position`, optional sender/speaker and timestamp, metadata, and a required `SourceLocator`.

Future adapters should create units in source order and use a stable source ID for every locator. They should preserve the original text rather than replacing it with a summary.

## Provenance locators

`SourceLocator` supports the common fields needed by planned adapters:

- WhatsApp: `message_index`, timestamp, character offsets.
- PDF/DOCX/PPTX: `page_number`, `paragraph_index`, `block_index`, `slide_number`.
- Audio: `segment_index`, timestamp seconds, optional character offsets.
- Images/OCR: `block_index`, character offsets, and extensible metadata for regions.

All fields are optional except `source_id`. Ranges are validated so end values cannot precede start values. Unknown source-specific details can be retained in `metadata` without weakening the common fields.

## Example JSON

### WhatsApp

```json
{
  "source_id": "source-chat-1",
  "source_type": "whatsapp",
  "original_filename": "chat.txt",
  "processing_status": "completed",
  "units": [{
    "unit_id": "unit-1",
    "source_id": "source-chat-1",
    "content_type": "message",
    "text": "Asha will send the slides tomorrow.",
    "position": 0,
    "sender_or_speaker": "Rahul",
    "locator": {
      "source_id": "source-chat-1",
      "message_index": 12,
      "metadata": {"raw_line": 14}
    }
  }]
}
```

### Document

```json
{
  "source_id": "source-pdf-1",
  "source_type": "pdf",
  "original_filename": "brief.pdf",
  "processing_status": "partial",
  "warnings": ["Page 4 contains an unreadable table."],
  "units": [{
    "source_id": "source-pdf-1",
    "content_type": "paragraph",
    "text": "Project deadline: 8 October.",
    "position": 3,
    "locator": {
      "source_id": "source-pdf-1",
      "page_number": 2,
      "paragraph_index": 4
    }
  }]
}
```

### Image and audio

Images use `content_type: "ocr_block"` and retain region data in locator metadata. Audio uses `content_type: "transcript_segment"`, `segment_index`, and `timestamp_start_seconds`/`timestamp_end_seconds`.

## Validation and serialization

Pydantic validates enum values, non-negative positions and offsets, source ownership, unique unit IDs, ordered units, locator ranges, and bounded diagnostic lists. `model_dump()` and `model_dump_json()` preserve optional metadata and provenance; `model_validate_json()` restores the same model without database-specific types.

The existing storage module aliases its source document name to `CanonicalSource`, avoiding a second source model. No MongoDB connection or persistence behavior is introduced by Phase 1.
