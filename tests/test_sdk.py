import io
import pytest
from openpyxl import Workbook
from chunker_sdk import DocumentChunker, ChunkingConfig, detect_file_type, recommend_strategy
def test_pdf_detection_and_signature():
    assert detect_file_type("a.pdf", b"%PDF-1.4")["file_type"] == "pdf"
    with pytest.raises(ValueError): detect_file_type("a.pdf", b"not a pdf")
def test_text_and_unsupported_detection():
    assert detect_file_type("a.txt", b"hi")["extension"] == ".txt"
    with pytest.raises(ValueError, match="Unsupported"): detect_file_type("a.exe", b"x")
def test_config_bounds():
    assert ChunkingConfig(chunk_size=100, overlap=0).chunk_size == 100
    with pytest.raises(ValueError): ChunkingConfig(chunk_size=99, overlap=0)
    with pytest.raises(ValueError): ChunkingConfig(chunk_size=100, overlap=51)
    with pytest.raises(ValueError): ChunkingConfig(chunk_size=1000, overlap=1000)
def test_strategy_recommendations():
    assert recommend_strategy("a.csv","csv","id | amount").strategy == "table"
    assert recommend_strategy("a.py","code","def main(): return 1").strategy == "code"
def test_text_chunking_ids_metadata_and_size():
    text = ("First paragraph about payment disputes. " * 12) + "\n\n" + ("Second paragraph about reconciliation. " * 12)
    result = DocumentChunker().process("sample.txt", text.encode(), {"chunk_size":200,"overlap":40,"strategy":"auto"})
    assert result.total_chunks > 1
    assert [c.index for c in result.chunks] == list(range(result.total_chunks))
    assert all(c.document_id == result.document.document_id for c in result.chunks)
    assert all(c.metadata["filename"] == "sample.txt" for c in result.chunks)
    assert all(c.char_count == len(c.text) <= 200 for c in result.chunks)
def test_csv_preserves_rows():
    result = DocumentChunker().process("tx.csv", b"id,merchant,amount\n1,Acme,100\n2,Blue Meadow,200\n",
        {"chunk_size":300,"overlap":0,"strategy":"auto"})
    assert result.recommendation.strategy == "table"
    assert any("merchant: Acme" in c.text for c in result.chunks)
    assert any(c.metadata.get("sources") for c in result.chunks)
def test_xlsx_sheet_extraction():
    wb=Workbook(); ws=wb.active; ws.title="Transactions"; ws.append(["case","amount"]); ws.append(["CASE-100",1250])
    buf=io.BytesIO(); wb.save(buf)
    result=DocumentChunker().process("tx.xlsx",buf.getvalue(),{"chunk_size":300,"overlap":0,"strategy":"auto"})
    assert "Transactions" in result.document.sheet_names and "CASE-100" in result.extracted_text_preview
def test_empty_upload_rejected():
    with pytest.raises(ValueError,match="empty"): DocumentChunker().process("empty.txt",b"",{})

def test_preview_is_bounded_and_scores_candidates():
    text = ("# Settlement\n\nAmount and transaction status are reviewed.\n\n" * 30).encode()
    result = DocumentChunker().preview("report.md", text, {"chunk_size":200,"overlap":20,"strategy":"auto","preview_count":6})
    assert 5 <= len(result.preview_chunks) <= 10
    assert result.recommendation.candidate_scores
    assert result.trace["trace_id"]
    assert result.metrics["preview_chunk_count"] <= 10

def test_parent_child_emits_both_levels():
    text = ("# Section\n\n" + ("Detailed payment review content. " * 40) + "\n\n# Another section\n\n" + ("Settlement evidence. " * 30)).encode()
    result = DocumentChunker().process("notes.md", text, {"chunk_size":300,"overlap":30,"strategy":"parent_child"})
    types = {c.metadata.get("chunkType") for c in result.chunks}
    assert "parent" in types and "child" in types
    assert all(c.metadata.get("parentId") for c in result.chunks)
    assert all("parentContext" in c.metadata for c in result.chunks)

def test_html_table_is_preserved_and_recommended():
    html = b"<html><body><h1>Transactions</h1><table><tr><th>Case</th><th>Amount</th></tr><tr><td>C-100</td><td>200</td></tr></table></body></html>"
    result = DocumentChunker().process("table.html", html, {"chunk_size":300,"overlap":0,"strategy":"auto"})
    assert "C-100" in result.extracted_text_preview
    assert "|" in result.extracted_text_preview
    assert result.recommendation.strategy == "table"

def test_chunk_metadata_has_source_coordinates_and_hash():
    result = DocumentChunker().process("simple.txt", b"Heading\n\nA first paragraph with source context.\n\nA second paragraph.", {"chunk_size":100,"overlap":0,"strategy":"paragraph"})
    assert all("sourceDocument" in c.metadata and "startChar" in c.metadata and "contentHash" in c.metadata for c in result.chunks)
