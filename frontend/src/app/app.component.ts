import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

interface Chunk { chunk_id?: string; text: string; metadata?: Record<string, unknown>; }
interface ApiResult { document?: { filename?: string; document_id?: string; file_type?: string }; chunks: Chunk[]; total_chunks?: number; config?: { strategy?: string; chunk_size?: number; overlap?: number }; recommendation?: { selected_strategy?: string; rationale?: string; candidate_scores?: Record<string, number> }; warnings?: string[]; trace?: unknown; }
@Component({ selector: 'app-root', standalone: true, imports: [CommonModule, FormsModule], template: `
<div class="app-shell">
  <header class="topbar"><div class="brand"><div class="brand-mark">C</div><span>Intelligent Document Chunker Acceler-AI-te 2026<span class="brand-dot">.</span></span><span class="sdk-tag">SDK</span></div><div class="top-actions"><span class="status-dot"></span><span>Connected</span><span class="divider"></span><button class="icon-btn" title="API status" (click)="checkHealth()">↻</button><span class="avatar">DC</span></div></header>
  <aside class="sidebar"><div class="nav-caption">WORKSPACE</div><button class="nav-item active"><span class="nav-icon">▦</span> Chunk documents</button><button class="nav-item" (click)="activeTab='history'"><span class="nav-icon"></span></button><div class="side-bottom"><div class="version"></div></div></aside>
  <main class="main-content"><div class="page-heading"><div><div class="eyebrow">DOCUMENT INTELLIGENCE / CHUNKING</div><h1>Chunk your documents<span>.</span></h1><p class="subtitle">Turn long documents into structured, traceable chunks — ready for your downstream pipeline.</p></div><div class="heading-pill"></div></div>
  <div class="metrics-row"><div class="metric-card"><div class="metric-label">CURRENT DOCUMENT</div><div class="metric-value small-value">{{ file?.name || 'No document selected' }}</div><div class="metric-foot">{{ file ? formatSize(file.size) : 'Upload a file to get started' }}</div></div><div class="metric-card"><div class="metric-label">CHUNK COUNT</div><div class="metric-value">{{ result?.total_chunks ?? '—' }}</div><div class="metric-foot">{{ result ? 'Generated chunks' : 'Waiting for processing' }}</div></div><div class="metric-card"><div class="metric-label">STRATEGY</div><div class="metric-value strategy-value">{{ result?.config?.strategy || strategy }}</div><div class="metric-foot">{{ result?.recommendation ? 'Auto-selected recommendation' : 'Configurable chunking method' }}</div></div><div class="metric-card"><div class="metric-label">CONNECTION STATUS</div><div class="metric-value local-value">{{ healthStatus || 'OK' }}</div><div class="metric-foot"><span class="tiny-green-dot"></span>{{ healthStatus === '200' ? 'Connected' : 'Check API status' }}</div></div></div>
  <div class="workspace-grid"><section class="panel config-panel"><div class="panel-header"><div><span class="step-number">01</span><h2>Configure chunking</h2></div><span class="muted-label">SETTINGS</span></div>
  <label class="upload-zone" [class.has-file]="!!file" for="fileInput"><input id="fileInput" type="file" (change)="onFile($event)" accept=".pdf,.txt,.md,.csv,.xlsx,.xls,.docx,.json,.xml,.html,.py,.java,.js,.sql"/><span class="upload-symbol">↑</span><strong>{{ file?.name || 'Drop a document here' }}</strong><span>{{ file ? formatSize(file.size) + ' · Ready to process' : 'or click to browse files' }}</span><small>PDF · DOCX · TXT · MD · CSV · XLSX · JSON · XML · HTML · CODE</small></label>
  <div class="form-group"><label for="strategy">CHUNKING STRATEGY</label><select id="strategy" [(ngModel)]="strategy"><option value="auto">Auto — recommend best fit</option><option value="recursive">Recursive</option><option value="fixed">Fixed size</option><option value="semantic">Semantic</option><option value="sentence">Sentence</option><option value="paragraph">Paragraph</option><option value="table">Table-aware</option><option value="code">Code-aware</option><option value="parent_child">Parent-child</option><option value="sliding_window">Sliding window</option></select><p class="field-hint">Auto evaluates document structure and recommends a suitable strategy.</p></div>
  <div class="two-fields"><div class="form-group"><label for="chunkSize">CHUNK SIZE <b>{{ chunkSize | number }}</b></label><input id="chunkSize" type="range" min="100" max="10000" step="100" [(ngModel)]="chunkSize"/><div class="range-labels"><span>100 chars</span><span>10,000 chars</span></div></div><div class="form-group"><label for="overlap">OVERLAP <b>{{ overlap | number }}</b></label><input id="overlap" type="range" min="0" max="2000" step="25" [(ngModel)]="overlap"/><div class="range-labels"><span>0 chars</span><span>2,000 chars</span></div></div></div>
  <div class="info-strip"><span>ⓘ</span><p>Chunk size is measured in characters. Overlap must be no more than 50% of the chunk size.</p></div><div class="action-row"><button class="btn-secondary" [disabled]="!file || busy" (click)="run(true)">Preview chunks</button><button class="btn-primary" [disabled]="!file || busy" (click)="run(false)">{{ busy ? 'Processing…' : 'Process document' }} <span>→</span></button></div><p class="error-msg" *ngIf="error">{{ error }}</p><p class="success-msg" *ngIf="notice">{{ notice }}</p></section>
  <section class="panel results-panel"><div class="panel-header"><div><span class="step-number">02</span><h2>{{ result ? 'Chunk output' : 'Preview & output' }}</h2></div><div class="output-actions" *ngIf="result"><button class="small-btn" (click)="copyJson()">Copy JSON</button><button class="small-btn export-btn" (click)="downloadJson()">↓ Export</button></div></div>
  <div *ngIf="!result" class="empty-state"><div class="empty-illustration"><div class="doc-sheet"><i></i><i></i><i></i><i></i><span>✦</span></div><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div></div><h3>Your chunks will appear here</h3><p>Upload a document, preview the boundaries, then process the full file to inspect and export structured output.</p><div class="empty-features"><span>✓ Metadata included</span><span>✓ Character offsets</span><span>✓ JSON export</span></div></div>
  <div *ngIf="result" class="result-content"><div class="result-summary"><div><span class="result-kicker">DOCUMENT</span><strong>{{ result.document?.filename || file?.name }}</strong></div><div><span class="result-kicker">CHUNKS</span><strong>{{ result.total_chunks ?? result.chunks.length }}</strong></div><div><span class="result-kicker">MODE</span><strong>{{ isPreview ? 'Preview' : 'Full run' }}</strong></div></div><div class="recommendation" *ngIf="result.recommendation"><span class="recommendation-icon">✦</span><div><strong>Strategy recommendation</strong><p>{{ result.recommendation.rationale || ('Recommended strategy: ' + (result.recommendation.selected_strategy || strategy)) }}</p></div></div><div class="chunk-list"><article class="chunk-card" *ngFor="let chunk of result.chunks; let i = index"><div class="chunk-top"><span class="chunk-index">CHUNK {{ (i + 1).toString().padStart(2,'0') }}</span><span class="chunk-length">{{ chunk.text.length | number }} chars</span></div><pre>{{ chunk.text }}</pre><div class="chunk-meta"><span *ngFor="let item of metadataEntries(chunk.metadata) | slice:0:4"><b>{{ item[0] }}</b> {{ item[1] }}</span></div></article></div><div class="result-footer" *ngIf="result.warnings?.length"><span>ⓘ</span>{{ result.warnings?.join(' · ') }}</div></div></section></div>
  <footer class="page-footer"><span>Built for structured document workflows</span><span><i></i> CHUNKING API <b>OPERATIONAL</b></span></footer></main>
</div>
` })
export class AppComponent {
  private readonly apiUrl = 'https://gp-intelligent-document-chunker.onrender.com';
  healthStatus = '';
  file: File | null = null; strategy = 'auto'; chunkSize = 1000; overlap = 150; busy = false; result: ApiResult | null = null; isPreview = false; error = ''; notice = ''; activeTab = 'chunk';
  constructor(private http: HttpClient) {}
  onFile(event: Event) { const input = event.target as HTMLInputElement; this.file = input.files?.[0] ?? null; this.result = null; this.error = ''; this.notice = ''; }
  formatSize(bytes: number) { return bytes < 1024 ? `${bytes} B` : bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(2)} MB`; }
  run(preview: boolean) {
    if (!this.file) return;
    if (Number(this.overlap) > Number(this.chunkSize) * 0.5) {
      this.error = 'Overlap must be no more than 50% of the chunk size.';
      return;
    }

    this.busy = true;
    this.error = '';
    this.notice = '';
    const body = new FormData();
    body.append('file', this.file);
    body.append('strategy', this.strategy);
    body.append('chunk_size', String(this.chunkSize));
    body.append('overlap', String(this.overlap));
    if (preview) body.append('preview_count', '8');

    const endpoint = preview
      ? `${this.apiUrl}/v1/preview`
      : `${this.apiUrl}/v1/chunk`;

    this.http.post<ApiResult>(endpoint, body).subscribe({
      next: data => {
        this.result = data;
        this.isPreview = preview;
        this.busy = false;
        this.notice = preview
          ? 'Preview generated. Review boundaries before processing the full document.'
          : 'Document processed successfully. Output is ready to export.';
      },
      error: (e: HttpErrorResponse) => {
        this.busy = false;
        this.error = e.error?.detail || `API request failed (${e.status || 'network error'}). Check backend and CORS configuration.`;
      }
    });
  }
  metadataEntries(meta?: Record<string, unknown>): [string, string][] { return Object.entries(meta || {}).filter(([,v]) => v !== null && v !== undefined && typeof v !== 'object').map(([key, value]) => [key, String(value)]); }
  downloadJson() { if (!this.result) return; const blob = new Blob([JSON.stringify(this.result, null, 2)], {type:'application/json'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${this.file?.name || 'document'}.chunks.json`; a.click(); URL.revokeObjectURL(url); }
  copyJson() { if (!this.result) return; navigator.clipboard.writeText(JSON.stringify(this.result, null, 2)).then(() => this.notice = 'JSON copied to clipboard.').catch(() => this.error = 'Clipboard access was blocked by the browser.'); }
  checkHealth() { this.error = ''; this.http.get<unknown>(`${this.apiUrl}/health`).subscribe({ next: () => { this.healthStatus = '200'; this.notice = 'API connection is healthy.'; }, error: (e: HttpErrorResponse) => { this.healthStatus = String(e.status || 'ERR'); this.error = `API health check failed (${e.status || 'network error'}). Check backend URL and CORS configuration.`; } }); }
}
