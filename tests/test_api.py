from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
def test_health_and_config():
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/v1/config").json()["bounds"]["chunk_size"]["min"] == 100
def test_upload_txt():
    content=("A sample paragraph about document chunking. "*20).encode()
    r=client.post("/v1/chunk",data={"strategy":"auto","chunk_size":"200","overlap":"40"},
                  files={"file":("sample.txt",content,"text/plain")})
    assert r.status_code == 200, r.text
    data=r.json()
    assert data["document"]["extension"] == ".txt" and data["total_chunks"] > 1
    assert data["chunks"][0]["metadata"]["filename"] == "sample.txt"
def test_invalid_bounds_rejected():
    r=client.post("/v1/chunk",data={"strategy":"fixed","chunk_size":"100","overlap":"60"},
                  files={"file":("sample.txt",b"hello","text/plain")})
    assert r.status_code == 400

def test_preview_endpoint_returns_sample_and_trace():
    content = ("A paragraph about settlement quality.\n\n" * 40).encode()
    r = client.post("/v1/preview", data={"strategy":"auto","chunk_size":"200","overlap":"20","preview_count":"6"}, files={"file":("preview.txt",content,"text/plain")})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_preview"] is True
    assert 5 <= len(data["chunks"]) <= 10
    assert data["recommendation"]["candidate_scores"]
    assert data["trace"]["trace_id"]
    assert r.headers.get("x-trace-id")

def test_metrics_endpoints():
    assert client.get("/metrics").status_code == 200
    assert "document_chunker_calls_total" in client.get("/metrics/prometheus").text
