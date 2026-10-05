# Phase 3 — Document ingestion

The document ingestion boundary accepts PDF, DOCX, and PPTX uploads at
`POST /api/v1/sources/document`. The adapter writes the upload to a temporary
file, delegates conversion to Docling, and maps Docling's reading-order items
to the Phase 1 `CanonicalSource` model.

Each extracted `ContentUnit` preserves its source ID, content type, ordering,
page number, character span, and Docling label metadata when the converter
provides that provenance. If Docling returns no structured items but does
return plain text, the adapter emits a `partial` source with an explicit
warning. It never fabricates structured units.

Docling is imported lazily so the API can start and return a clear `503` when
the optional document runtime is not installed. Unsupported extensions and
empty uploads are reported as validation/conversion failures. The endpoint is
not persisted to MongoDB and does not invoke inference; those concerns belong
to later phases.

The implementation follows Docling's public `DocumentConverter` and
`DoclingDocument.iterate_items()` APIs:

- [DocumentConverter reference](https://docling-project.github.io/docling/reference/document_converter/)
- [DoclingDocument reference](https://docling-project.github.io/docling/reference/docling_document/)
- [Docling serialization guidance](https://docling-project.github.io/docling/concepts/serialization/)

The development environment now has Docling installed. Real conversion tests
pass for generated PDF, DOCX, and PPTX fixtures. PDF page provenance and PPTX
slide provenance are asserted against extracted content. OCR/scanned-document
support is intentionally not claimed by this phase.
