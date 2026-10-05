"""Parser and canonical adapter for WhatsApp text exports.

The parser is intentionally dependency-free. It supports the common Android
and iOS export shapes while retaining unrecognized lines as warnings instead
of silently dropping them.
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from typing import Any

from app.source.models import CanonicalSource, ContentType, ContentUnit, ExtractionMetadata, ProcessingStatus, SourceLocator, SourceType


MESSAGE_START = re.compile(
    r"^\s*\[?(?P<date>\d{1,4}[/-]\d{1,2}[/-]\d{1,4}),?\s+"
    r"(?P<time>\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?)\]?\s*(?:-\s+)?(?P<body>.*)$"
)
MEDIA_MARKERS = ("<media omitted>", "<image omitted>", "image omitted", "video omitted", "audio omitted")
DELETED_MARKERS = ("this message was deleted", "you deleted this message")
EXPORT_HEADER = re.compile(r"^(WhatsApp Chat\b|Exported:\s*|All names, messages, dates, and details below are fictional)", re.IGNORECASE)


@dataclass
class ParsedMessage:
    timestamp: datetime | None
    sender: str | None
    text: str
    message_index: int
    line_start: int
    line_end: int
    content_type: ContentType
    warnings: list[str]


def _parse_timestamp(date_text: str, time_text: str) -> tuple[datetime | None, str | None]:
    date_parts = [int(part) for part in re.split(r"[/-]", date_text)]
    warning = None
    if len(date_parts[0:2]) == 2 and date_parts[0] <= 12 and date_parts[1] <= 12:
        warning = f"Ambiguous date format at {date_text}; interpreted as day/month."
    if date_parts[0] > 12:
        day, month = date_parts[0], date_parts[1]
    elif date_parts[1] > 12:
        month, day = date_parts[0], date_parts[1]
    else:
        day, month = date_parts[0], date_parts[1]
    year = date_parts[2]
    year += 2000 if year < 100 else 0
    normalized_time = re.sub(r"\s+", " ", time_text.strip().upper())
    formats = ["%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"]
    parsed_time = None
    for time_format in formats:
        try:
            parsed_time = datetime.strptime(normalized_time, time_format).time()
            break
        except ValueError:
            continue
    if parsed_time is None:
        return None, f"Unsupported timestamp time: {time_text}"
    try:
        return datetime(year, month, day, parsed_time.hour, parsed_time.minute, parsed_time.second), warning
    except ValueError:
        return None, f"Invalid calendar date: {date_text}"


def _classify(sender: str | None, text: str) -> ContentType:
    folded = text.strip().casefold()
    if any(marker in folded for marker in MEDIA_MARKERS):
        return ContentType.MEDIA
    if any(marker in folded for marker in DELETED_MARKERS):
        return ContentType.DELETED
    if sender is None:
        return ContentType.SYSTEM
    return ContentType.MESSAGE


def _start_message(match: re.Match[str], message_index: int, line_number: int) -> ParsedMessage:
    timestamp, timestamp_warning = _parse_timestamp(match.group("date"), match.group("time"))
    body = match.group("body")
    sender = None
    text = body
    if ":" in body:
        possible_sender, separator, possible_text = body.partition(":")
        if possible_sender.strip():
            sender = possible_sender.strip()
            text = possible_text.lstrip()
    warnings = [timestamp_warning] if timestamp_warning else []
    return ParsedMessage(timestamp, sender, text, message_index, line_number, line_number, _classify(sender, text), warnings)


def parse_whatsapp_text(text: str, *, filename: str | None = None, file_size_bytes: int | None = None) -> CanonicalSource:
    """Parse a WhatsApp export into a provenance-preserving canonical source."""
    if not isinstance(text, str) or not text.strip():
        return CanonicalSource(
            source_type=SourceType.WHATSAPP,
            original_filename=filename,
            file_size_bytes=file_size_bytes,
            processing_status=ProcessingStatus.FAILED,
            errors=["The WhatsApp export is empty."],
            extraction=ExtractionMetadata(method="whatsapp_text_parser", status=ProcessingStatus.FAILED, errors=["The WhatsApp export is empty."]),
        )

    source_material = f"{filename or ''}\0{text}"
    source_id = f"whatsapp-{hashlib.sha256(source_material.encode('utf-8')).hexdigest()[:24]}"
    parsed: list[ParsedMessage] = []
    warnings: list[str] = []
    preamble: list[str] = []
    current: ParsedMessage | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        match = MESSAGE_START.match(raw_line)
        if match:
            if current:
                parsed.append(current)
            current = _start_message(match, len(parsed) + 1, line_number)
            warnings.extend(w for w in current.warnings if w not in warnings)
            continue
        if current is not None:
            current.text += "\n" + raw_line
            current.line_end = line_number
        elif raw_line.strip():
            if EXPORT_HEADER.match(raw_line.strip()):
                preamble.append(raw_line.strip())
            else:
                warnings.append(f"Unrecognized content before the first message at line {line_number}.")
    if current:
        parsed.append(current)
    for item in parsed:
        item.content_type = _classify(item.sender, item.text)
        if item.line_end > item.line_start:
            item.warnings.append("Multiline message preserved.")
    units = [
        ContentUnit(
            source_id=source_id,
            content_type=item.content_type,
            text=item.text,
            position=index,
            timestamp=item.timestamp,
            sender_or_speaker=item.sender,
            locator=SourceLocator(
                source_id=source_id,
                message_index=item.message_index,
                metadata={"line_start": item.line_start, "line_end": item.line_end, "classification": item.content_type.value},
            ),
            metadata={"warnings": item.warnings},
        )
        for index, item in enumerate(parsed)
    ]
    participants = sorted({item.sender for item in parsed if item.sender})
    parse_errors = [warning for warning in warnings if warning.startswith("Unrecognized")]
    status = ProcessingStatus.COMPLETED if parsed and not warnings else ProcessingStatus.PARTIAL if parsed else ProcessingStatus.FAILED
    extraction = ExtractionMetadata(method="whatsapp_text_parser", tool="built-in", status=status, warnings=warnings, errors=parse_errors, metadata={"format": "whatsapp_text"})
    return CanonicalSource(
        source_id=source_id,
        source_type=SourceType.WHATSAPP,
        original_filename=filename,
        mime_type="text/plain",
        file_size_bytes=file_size_bytes,
        original_metadata={"participants": participants, "message_count": len(parsed), "system_count": sum(unit.content_type is ContentType.SYSTEM for unit in units), "media_count": sum(unit.content_type is ContentType.MEDIA for unit in units), "deleted_count": sum(unit.content_type is ContentType.DELETED for unit in units), "preamble": preamble},
        processing_status=status,
        warnings=warnings,
        errors=parse_errors,
        units=units,
        extraction=extraction,
    )
