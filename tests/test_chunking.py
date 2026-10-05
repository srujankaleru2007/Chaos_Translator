from app.inference.chunking import split_source


def test_whatsapp_chunks_preserve_all_messages_and_multiline_text():
    source = "01/01/2026, 10:00 - Asha: first\ncontinuation\n01/01/2026, 10:01 - Ravi: second\n"
    chunks = split_source(source, max_chars=45)
    assert "".join(chunks) == source
    assert len(chunks) == 2
    assert "continuation" in chunks[0]


def test_short_source_is_single_chunk():
    assert split_source("a\nb\n") == ["a\nb\n"]
