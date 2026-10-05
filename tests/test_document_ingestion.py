from types import SimpleNamespace
from io import BytesIO
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ingestion.documents import DoclingUnavailable, DocumentIngestionError, convert_document_bytes
from app.source.models import ContentType, ProcessingStatus, SourceType


class FakeItem:
    def __init__(self, text, label, page=1, charspan=(0, 10)):
        self.text = text
        self.label = SimpleNamespace(value=label)
        self.prov = [SimpleNamespace(page_no=page, charspan=charspan, bbox=None)]


class FakeDocument:
    def __init__(self, items=None, text=""):
        self.items = items or []
        self.text = text

    def iterate_items(self):
        return [(item, 0) for item in self.items]

    def export_to_text(self):
        return self.text


class FakeConverter:
    def __init__(self, document):
        self.document = document
        self.paths = []

    def convert(self, path):
        self.paths.append(path)
        return SimpleNamespace(document=self.document)


def sample_bytes(filename):
    if filename.endswith(".pdf"):
        return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml" if filename.endswith(".docx") else "ppt/presentation.xml", "<document/>")
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "source_type"),
    [("brief.pdf", SourceType.PDF), ("brief.docx", SourceType.DOCX), ("brief.pptx", SourceType.PPTX)],
)
def test_supported_documents_map_to_canonical_source(filename, source_type):
    converter = FakeConverter(FakeDocument([FakeItem("Heading", "section_header", page=2), FakeItem("A paragraph", "text", page=2, charspan=(12, 23))]))

    source = convert_document_bytes(sample_bytes(filename), filename=filename, converter=converter)

    assert source.source_type == source_type
    assert source.processing_status == ProcessingStatus.COMPLETED
    assert source.extraction.tool == "docling"
    assert [unit.content_type for unit in source.units] == [ContentType.HEADING, ContentType.PARAGRAPH]
    assert (source.units[1].locator.slide_number if source_type is SourceType.PPTX else source.units[1].locator.page_number) == 2
    assert source.units[1].locator.character_start == 12
    assert source.units[1].locator.character_end == 23


def test_docling_plain_text_fallback_is_explicitly_partial():
    source = convert_document_bytes(sample_bytes("brief.pdf"), filename="brief.pdf", converter=FakeConverter(FakeDocument(text="Fallback text")))

    assert source.processing_status == ProcessingStatus.PARTIAL
    assert source.warnings
    assert source.units[0].locator.metadata["fallback"] == "export_to_text"


def test_empty_document_is_failed_without_fabricated_content():
    source = convert_document_bytes(b"", filename="empty.pdf", converter=FakeConverter(FakeDocument()))

    assert source.processing_status == ProcessingStatus.FAILED
    assert source.units == []
    assert source.errors == ["The document is empty."]


def test_unsupported_extension_is_rejected():
    with pytest.raises(DocumentIngestionError, match="Only PDF, DOCX, and PPTX"):
        convert_document_bytes(b"bytes", filename="notes.txt", converter=FakeConverter(FakeDocument()))


@pytest.mark.parametrize("filename", ["brief.pdf", "brief.docx", "brief.pptx"])
def test_signature_and_mime_validation_rejects_mismatched_payloads(filename):
    with pytest.raises(DocumentIngestionError, match="signature|ZIP|PDF"):
        convert_document_bytes(b"not a real document", filename=filename, converter=FakeConverter(FakeDocument()))
    with pytest.raises(DocumentIngestionError, match="MIME"):
        convert_document_bytes(sample_bytes(filename), filename=filename, declared_mime_type="text/plain", converter=FakeConverter(FakeDocument()))


def test_document_size_limit_is_enforced():
    from app.ingestion.documents import MAX_DOCUMENT_SIZE_BYTES

    with pytest.raises(DocumentIngestionError, match="25 MiB"):
        convert_document_bytes(b"%PDF-" + b"x" * MAX_DOCUMENT_SIZE_BYTES, filename="large.pdf", converter=FakeConverter(FakeDocument()))


def test_missing_docling_is_reported_as_dependency_failure(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "docling.document_converter":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with pytest.raises(DoclingUnavailable, match="Docling is not installed"):
        convert_document_bytes(sample_bytes("brief.pdf"), filename="brief.pdf")


def test_document_endpoint_rejects_unsupported_upload():
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/document", files={"file": ("notes.txt", b"text", "text/plain")})

    assert response.status_code == 422
    assert "PDF, DOCX, and PPTX" in response.json()["detail"]


def test_document_endpoint_exposes_missing_docling_as_503(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "docling.document_converter":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    with TestClient(app) as client:
        response = client.post("/api/v1/sources/document", files={"file": ("brief.pdf", sample_bytes("brief.pdf"), "application/pdf")})

    assert response.status_code == 503
    assert "Docling is not installed" in response.json()["detail"]
