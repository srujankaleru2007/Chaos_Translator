# Phase 4 — Image and screenshot OCR

Image ingestion is available at `POST /api/v1/sources/image` for PNG, JPEG,
WEBP, BMP, and TIFF uploads. Uploads are bounded to 10 MiB and validated with
Pillow before OCR. Declared MIME types are checked against the extension and
actual image structure.

The adapter uses Docling first. Extracted text becomes canonical
`ContentType.OCR_BLOCK` units, with Docling bounding boxes preserved in the
unit locator metadata when available. If Docling fails or returns no text, the
adapter attempts a controlled PyTesseract fallback with a timeout. The
fallback is optional and reports a clear failed status when the Python package
or Tesseract executable is unavailable.

Fallback output is marked `partial` and includes a warning because OCR text and
coordinates need verification against the source image. OCR errors do not
expose source content or executable details to clients.

This phase does not add frontend source lifecycle work, image anonymization,
or scanned-PDF OCR. Those remain separate concerns.
