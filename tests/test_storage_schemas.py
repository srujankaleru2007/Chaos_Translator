from datetime import datetime, timezone

from app.inference.schemas import ExtractionResult
from app.storage.schemas import ExtractionDocument, SourceDocument, mongo_document


def test_source_document_is_workspace_scoped_and_bson_serializable():
    document = SourceDocument(workspace_id="workspace-1", source_type="whatsapp")
    dumped = mongo_document(document)

    assert dumped["workspace_id"] == "workspace-1"
    assert isinstance(dumped["ingested_at"], datetime)
    assert dumped["ingested_at"].tzinfo == timezone.utc


def test_extraction_document_preserves_typed_result():
    result = ExtractionResult(summary="Nothing actionable.")
    document = ExtractionDocument(workspace_id="workspace-1", source_id="source-1", result=result)

    dumped = mongo_document(document)

    assert dumped["result"]["summary"] == "Nothing actionable."
    assert dumped["result"]["tasks"] == []
