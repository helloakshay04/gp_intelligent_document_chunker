# Baseline scenarios and acceptance checks (SDK 1.1.0)

- Empty uploads are rejected with a readable error; unsupported extensions and obvious signature mismatches are rejected.
- Config validates chunk size (100–10,000 chars), overlap (0–2,000 chars, under chunk size and at most 50%), and preview count (5–10).
- Auto recommendation analyzes extension **and extracted content**: table-like rows/Markdown or HTML tables, code declarations/fences, headings, paragraphs, and sentence density.
- Auto evaluates candidate chunkers on a bounded sample and scores size utilization, boundary preservation, and structural fit. This is a heuristic quality proxy, not a retrieval-quality guarantee.
- PDF page, CSV row, XLSX sheet/row, DOCX paragraph/table, Markdown line/heading, and generic source coordinates are carried into chunk metadata when available.
- HTML script/style content is discarded; table rows are normalized to pipe-delimited lines, and nested table signals are detected by the extractor.
- Preview emits 5–10 chunks from a bounded sample, candidate scores, trace ID and duration metrics. Full processing is a separate API call.
- Parent-child returns both parent context chunks and child chunks with parent IDs and parent text metadata.
- API has JSON structured logs, trace IDs, named spans, per-call timing, `/metrics` JSON, and `/metrics/prometheus` output.
- Malformed JSON/XML, scanned PDFs, legacy XLS, empty workbooks, extraction failures and large files produce warnings or actionable errors rather than silent success.

## Retrieval-quality tuning boundary

The built-in selector runs a candidate bake-off with local structural proxies. Its confidence is a heuristic, not a measured probability of successful chunking.
