from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.ingestion.images import ImageIngestionError, OcrUnavailable, convert_image_bytes
from app.source.models import ContentType, ProcessingStatus


def png_bytes() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (160, 80), "white")
    image.save(output, format="PNG")
    return output.getvalue()


class FakeConverter:
    def __init__(self):
        item = SimpleNamespace(text="Screenshot text", prov=[SimpleNamespace(bbox=SimpleNamespace(model_dump=lambda mode: {"l": 1, "t": 2, "r": 30, "b": 20}))])
        self.document = SimpleNamespace(iterate_items=lambda: [(item, 0)])

    def convert(self, path):
        return SimpleNamespace(document=self.document)


class FailingConverter:
    def convert(self, path):
        raise RuntimeError("controlled Docling failure")


def test_docling_is_primary_and_preserves_ocr_bbox():
    fallback_called = False

    def fallback(data, timeout):
        nonlocal fallback_called
        fallback_called = True
        return []

    source = convert_image_bytes(png_bytes(), filename="screen.png", converter=FakeConverter(), ocr_runner=fallback)

    assert source.processing_status == ProcessingStatus.COMPLETED
    assert source.extraction.tool == "docling"
    assert source.units[0].content_type == ContentType.OCR_BLOCK
    assert source.units[0].locator.metadata["bbox"]["l"] == 1
    assert fallback_called is False


def test_pytesseract_fallback_is_partial_and_preserves_coordinates():
    source = convert_image_bytes(png_bytes(), filename="screen.png", converter=FailingConverter(), ocr_runner=lambda data, timeout: [{"text": "Fallback text", "bbox": {"left": 4, "top": 5, "width": 50, "height": 12}, "confidence": "91"}])

    assert source.processing_status == ProcessingStatus.PARTIAL
    assert source.extraction.tool == "pytesseract"
    assert source.units[0].text == "Fallback text"
    assert source.units[0].locator.metadata["bbox"]["width"] == 50
    assert any("fallback" in warning.casefold() for warning in source.warnings)


def test_unavailable_ocr_returns_failed_source_without_hiding_error():
    source = convert_image_bytes(png_bytes(), filename="screen.png", converter=FailingConverter(), ocr_runner=lambda data, timeout: (_ for _ in ()).throw(OcrUnavailable("Tesseract unavailable")))

    assert source.processing_status == ProcessingStatus.FAILED
    assert source.errors == ["Tesseract unavailable"]


@pytest.mark.parametrize("filename", ["screen.jpg", "screen.webp", "screen.tiff"])
def test_supported_image_extensions_are_signature_validated(filename):
    with pytest.raises(ImageIngestionError, match="signature|structure"):
        convert_image_bytes(b"not an image", filename=filename, converter=FakeConverter())


def test_mismatched_mime_is_rejected():
    with pytest.raises(ImageIngestionError, match="MIME"):
        convert_image_bytes(png_bytes(), filename="screen.png", declared_mime_type="image/jpeg", converter=FakeConverter())


def test_image_endpoint_rejects_invalid_signature():
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/image", files={"file": ("screen.png", b"not an image", "image/png")})

    assert response.status_code == 422
    assert "signature" in response.json()["detail"]
