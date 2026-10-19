from chunker_sdk import DocumentChunker, ChunkingConfig
engine = DocumentChunker(max_file_bytes=25*1024*1024)
with open("sample_document.pdf","rb") as f:
    result = engine.process("sample_document.pdf", f.read(), ChunkingConfig(strategy="auto",chunk_size=1000,overlap=150))
print("SDK:",result.sdk_version,"type:",result.document.file_type,"strategy:",result.recommendation.strategy,"chunks:",result.total_chunks)
for chunk in result.chunks: print(chunk.chunk_id,chunk.char_count,chunk.metadata)
