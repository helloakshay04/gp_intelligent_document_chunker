# gp_intelligent_document_chunker


## Match Engine — persistent ChromaDB embeddings

The Match Engine stores case-record embeddings in a local persistent ChromaDB database.
The default database directory is `./chroma_db` at the project root. Set `CHROMA_DB_PATH`
to use another directory or a mounted persistent volume.

Install dependencies:

```bash
pip install -e ".[api]"
```

Each workbook filename and embedding model combination receives its own ChromaDB collection.
When Match Engine runs, case vectors are inserted or updated only when a row's searchable
content changes, and vectors for rows removed from the workbook are deleted. Similarity
search uses ChromaDB results together with extracted-field comparisons. Back up the
`chroma_db` directory if you need to retain the vector index across machines or deployments.


## Match Engine dashboard and backend configuration

The Match Engine uses the project-managed case workbook at `data/case_records.xlsx` by default.
There is no Excel upload control in the UI. Replace or maintain this workbook in the project
folder to change the case records. Matched document names are written back to this workbook.

Configure credentials and model selection on the backend only:

```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-key"
$env:MATCH_ENGINE_LLM_MODEL="gpt-5"
$env:MATCH_ENGINE_EMBEDDING_MODEL="text-embedding-3-small"
uvicorn app.main:app --reload
```

Optional paths:
- `MATCH_ENGINE_CASE_WORKBOOK`: override the project case workbook path.
- `MATCH_ENGINE_DB_PATH`: path for persistent document history and dashboard analytics SQLite database.
- `CHROMA_DB_PATH`: path for persistent ChromaDB vectors.

The Match Engine dashboard includes total documents, total chunks, recent document history,
quality trend, chunk strategy distribution, and pipeline status. The quality trend is a heuristic
indicator based on chunk output balance, not a semantic quality evaluation.
