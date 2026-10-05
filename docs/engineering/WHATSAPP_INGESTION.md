# WhatsApp ingestion

Phase 2 adds a dependency-free adapter in `app/ingestion/whatsapp.py` and exposes it through `POST /api/v1/sources/whatsapp`.

## Supported input

The adapter accepts WhatsApp text exports with the common Android shape:

```text
12/05/2023, 10:30 - Alice: Hello
```

and the common bracketed iOS shape:

```text
[05/12/2023, 10:30:00 AM] Alice: Hello
```

The parser preserves multiline messages, Unicode and emoji, URLs, group sender names, system notifications, media placeholders, deleted-message placeholders, and messages without a sender. It supports 12-hour and 24-hour times, optional seconds, two- or four-digit years, and slash or hyphen date separators.

Ambiguous numeric dates are interpreted as day/month and produce a warning. Invalid timestamps do not discard the message; the message is retained with a null timestamp and a partial extraction status. Unknown content before the first recognized message is reported as a warning/error.

## Canonical mapping

Each parsed message becomes one `ContentUnit` in a `CanonicalSource`:

- `source_type`: `whatsapp`
- `position`: zero-based original message order
- `locator.message_index`: one-based WhatsApp message index
- `locator.metadata`: original line range and classification
- `timestamp`: parsed message timestamp when valid
- `sender_or_speaker`: sender name when present
- `content_type`: `message`, `system`, `media`, or `deleted`
- `metadata.warnings`: message-local warnings

The source metadata includes participants and message-type counts. The source ID is deterministic for the same input text, and generated unit IDs remain independent of array position.

## API

`POST /api/v1/sources/whatsapp`

```json
{
  "text": "12/05/2023, 10:30 - Alice: Hello",
  "filename": "chat.txt",
  "file_size_bytes": 42
}
```

The response is the complete `CanonicalSource` JSON representation. Empty input is rejected with HTTP 422. A non-empty export with some parseable messages returns `partial` status and preserves warnings/errors alongside successful units.

The active frontend reads `.txt` files locally, sends the text to this endpoint before extraction, and displays the parsed message preview. It does not send private file contents anywhere other than the configured backend.

## Limitations

- Locale-specific date ambiguity cannot always be resolved from a numeric export alone.
- Localized system/deleted/media phrases are not exhaustively classified; unknown phrases remain system or regular text without invented metadata.
- The adapter does not extract attached media files from an export; it preserves WhatsApp placeholders.
- No database persistence, document ingestion, OCR, audio transcription, or cross-source linking is part of Phase 2.

## Attribution

The implementation is an independent, dependency-free adapter informed by the public capabilities of [whatsapp-chat-analyzer](https://github.com/mtmxo/whatsapp-chat-analyzer), which is MIT licensed. No repository code was copied into this project.
