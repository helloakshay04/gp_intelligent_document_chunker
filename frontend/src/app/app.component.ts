import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

interface Chunk { chunk_id?: string; text: string; metadata?: Record<string, unknown>; }
interface MatchItem { document: string; status: string; error?: string; matched_case_number?: string | null; confidence?: number; extracted_fields?: Record<string, unknown>; match_method?: string; chunks_created?: number; }
interface MatchResponse { results: MatchItem[]; summary: { processed: number; matched: number; unmatched: number; errors: number }; case_database?: string; embedding_store?: { type: string; collection: string; persist_directory: string; records: number; persistent: boolean }; }
interface DashboardDocument { document_name:string; type:string; pages:number; status:string; strategy:string; uploaded_at:string; chunks:number; quality_score:number; chunk_size:number; error?:string|null; }
interface MatchDashboard { total_documents:number; total_chunks:number; average_quality:number; recent_documents:DashboardDocument[]; quality_trend:{date:string;quality:number;documents:number}[]; chunk_distribution:{strategy:string;count:number}[]; processing_pipeline:{name:string;status:string}[]; case_database:{filename:string;available:boolean;records:number}; }
interface ApiResult { document?: { filename?: string; document_id?: string; file_type?: string }; chunks: Chunk[]; total_chunks?: number; config?: { strategy?: string; chunk_size?: number; overlap?: number }; recommendation?: { selected_strategy?: string; rationale?: string; candidate_scores?: Record<string, number> }; warnings?: string[]; trace?: unknown; }
@Component({ selector: 'app-root', standalone: true, imports: [CommonModule, FormsModule], template: `
<div class="app-shell">
  <header class="topbar"><div class="brand"><div class="brand-mark">C</div><span>Intelligent Document Chunker<span class="brand-dot">.</span></span><span class="sdk-tag">SDK</span></div><div class="top-actions"><span class="status-dot"></span><span>Connected</span><span class="divider"></span><button class="icon-btn" title="API status" (click)="checkHealth()">↻</button><span class="avatar">DC</span></div></header>
  <aside class="sidebar"><div class="nav-caption">WORKSPACE</div><button class="nav-item" [class.active]="activeTab==='chunk'" (click)="activeTab='chunk'"><span class="nav-icon">▦</span> Chunk documents</button><button class="nav-item" [class.active]="activeTab==='match'" (click)="activeTab='match'; loadMatchDashboard()"><span class="nav-icon">⇄</span> Match Engine</button><button class="nav-item" [class.active]="activeTab==='about'" (click)="activeTab='about'"><span class="nav-icon">✦</span> About us</button><div class="side-bottom"><div class="version"></div></div></aside>
  <main class="main-content"><div class="page-heading" *ngIf="activeTab!=='match'"><div><div class="eyebrow">DOCUMENT INTELLIGENCE / CHUNKING</div><h1>Chunk your documents<span>.</span></h1><p class="subtitle">Turn long documents into structured, traceable chunks — ready for your downstream pipeline.</p></div><div class="heading-pill"></div></div>
  <section *ngIf="activeTab==='match'" class="match-dashboard">
    <div class="dashboard-heading"><div><span class="eyebrow">DOCUMENT INTELLIGENCE / RECONCILIATION</span><h1>Match Engine<span>.</span></h1><p class="subtitle">Chunk PDFs, extract case attributes, search the project case database, and link documents to the right case.</p></div><button class="btn-secondary" (click)="loadMatchDashboard()">↻ Refresh dashboard</button></div>
    <div class="metrics-row match-metrics">
      <div class="metric-card"><div class="metric-label">TOTAL DOCUMENTS</div><div class="metric-value">{{ matchDashboard?.total_documents ?? 0 }}</div><div class="metric-foot">Documents processed</div></div>
      <div class="metric-card"><div class="metric-label">TOTAL CHUNKS</div><div class="metric-value">{{ matchDashboard?.total_chunks ?? 0 }}</div><div class="metric-foot">Across processed documents</div></div>
      <div class="metric-card"><div class="metric-label">AVG. CHUNKING QUALITY</div><div class="metric-value">{{ (matchDashboard?.average_quality ?? 0) | number:'1.0-1' }}<small>%</small></div><div class="metric-foot">Heuristic quality indicator</div></div>
      <div class="metric-card"><div class="metric-label">CASE DATABASE RECORDS</div><div class="metric-value">{{ matchDashboard?.case_database?.records ?? 0 }}</div><div class="metric-foot">{{ matchDashboard?.case_database?.filename || 'case_records.xlsx' }} · {{ matchDashboard?.case_database?.available ? 'Connected' : 'File missing' }}</div></div>
    </div>
    <div class="match-layout">
      <section class="panel match-config">
        <div class="panel-header"><div><span class="step-number">01</span><h2>Process documents</h2></div><span class="muted-label">SDK + AI</span></div>
        <p class="field-hint">Upload PDFs or a ZIP containing PDFs. The case workbook and AI configuration are managed by the backend.</p>
        <label class="upload-zone" for="matchDocs"><input id="matchDocs" type="file" multiple accept=".pdf,.zip" (change)="onMatchDocs($event)"/><span class="upload-symbol">↑</span><strong>{{ matchFiles.length ? matchFiles.length + ' file(s) selected' : 'Upload PDF files or ZIP' }}</strong><span>{{ matchFilesLabel || 'PDF · ZIP containing PDFs' }}</span></label>
        <div class="form-group"><label>CHUNK STRATEGY</label><select [(ngModel)]="matchStrategy"><option value="auto">Auto — recommend best fit</option><option value="recursive">Recursive</option><option value="semantic">Semantic</option><option value="fixed">Fixed size</option><option value="paragraph">Paragraph</option><option value="sentence">Sentence</option><option value="table">Table-aware</option><option value="code">Code-aware</option><option value="parent_child">Parent-child</option><option value="sliding_window">Sliding window</option></select></div>
        <div class="form-group"><label>CHUNK SIZE <b>{{ matchChunkSize | number }} characters</b></label><input type="range" min="100" max="10000" step="100" [(ngModel)]="matchChunkSize"/><div class="range-labels"><span>100</span><span>10,000</span></div></div>
        <div class="info-strip"><span>ⓘ</span><p>OpenAI credentials, LLM selection, embedding model, ChromaDB, and Excel case database are configured on the backend.</p></div>
        <div class="action-row"><button class="btn-primary" [disabled]="matchBusy || !matchFiles.length" (click)="runMatchEngine()">{{ matchBusy ? 'Processing documents…' : 'Run Match Engine →' }}</button></div>
        <p class="error-msg" *ngIf="matchError">{{ matchError }}</p><p class="success-msg" *ngIf="matchNotice">{{ matchNotice }}</p>
        <div class="pipeline"><h3>Processing pipeline</h3><div class="pipeline-step" *ngFor="let step of matchDashboard?.processing_pipeline; let i=index"><span class="pipeline-number">{{ i+1 }}</span><span>{{ step.name }}</span><small>{{ step.status }}</small></div></div>
      </section>
      <div class="dashboard-right">
        <section class="panel chart-panel"><div class="panel-header"><div><span class="step-number">02</span><h2>Chunking quality trend</h2></div><span class="muted-label">LAST 7 ACTIVE DAYS</span></div>
          <div class="quality-chart" *ngIf="matchDashboard?.quality_trend?.length; else noTrend"><div class="quality-col" *ngFor="let point of matchDashboard?.quality_trend"><div class="quality-bar-wrap"><div class="quality-bar" [style.height.%]="point.quality"></div></div><b>{{ point.quality }}%</b><span>{{ point.date | date:'MMM d' }}</span></div></div>
          <ng-template #noTrend><div class="chart-empty">Quality trend appears after documents are processed.</div></ng-template><p class="field-hint">Heuristic score based on non-empty and balanced chunk output, not an LLM evaluation.</p>
        </section>
        <section class="panel chart-panel"><div class="panel-header"><div><span class="step-number">03</span><h2>Chunk distribution</h2></div><span class="muted-label">BY STRATEGY</span></div>
          <div class="pie-charts-grid">
            <div class="pie-chart-card">
              <h4>Strategy share</h4>
              <div class="pie-chart" [style.background]="strategyPieGradient()" role="img" aria-label="Chunk strategy distribution pie chart"></div>
              <div class="pie-legend" *ngIf="matchDashboard?.chunk_distribution?.length; else noDistributionLegend">
                <div *ngFor="let item of matchDashboard?.chunk_distribution; let i=index"><i [style.background]="pieColor(i)"></i><span>{{ item.strategy }}</span><b>{{ item.count }}</b></div>
              </div>
              <ng-template #noDistributionLegend><p class="pie-empty">No strategy data yet</p></ng-template>
            </div>
            <div class="pie-chart-card">
              <h4>Document status</h4>
              <div class="pie-chart" [style.background]="statusPieGradient()" role="img" aria-label="Document processing status pie chart"></div>
              <div class="pie-legend">
                <div><i style="background:#18a6a0"></i><span>Matched</span><b>{{ statusCount('matched') }}</b></div>
                <div><i style="background:#3978d4"></i><span>Unmatched</span><b>{{ statusCount('unmatched') }}</b></div>
                <div><i style="background:#e46d69"></i><span>Error</span><b>{{ statusCount('error') }}</b></div>
                <div><i style="background:#9aa7b7"></i><span>Other</span><b>{{ statusCount('other') }}</b></div>
              </div>
            </div>
          </div>
          <ng-template #noDistribution><div class="chart-empty">Strategy distribution appears after documents are processed.</div></ng-template>
        </section>
      </div>
    </div>
    <section class="panel recent-panel"><div class="panel-header"><div><span class="step-number">04</span><h2>Recent documents</h2></div><span class="muted-label">{{ matchDashboard?.recent_documents?.length || 0 }} RECORDS</span></div>
      <div class="table-wrap"><table class="recent-table"><thead><tr><th>DOCUMENT NAME</th><th>TYPE</th><th>PAGES</th><th>STATUS</th><th>STRATEGY</th><th>UPLOADED AT</th><th>CHUNKS</th></tr></thead><tbody><tr *ngFor="let doc of matchDashboard?.recent_documents"><td class="doc-name">{{ doc.document_name }}</td><td>{{ doc.type | uppercase }}</td><td>{{ doc.pages || '—' }}</td><td><span class="status-pill" [class.status-matched]="doc.status==='matched'" [class.status-error]="doc.status==='error'">{{ doc.status }}</span></td><td>{{ doc.strategy }}</td><td>{{ doc.uploaded_at | date:'MMM d, y, HH:mm:ss' }}</td><td>{{ doc.chunks }}</td></tr></tbody></table></div>
      <div class="chart-empty" *ngIf="!matchDashboard?.recent_documents?.length">No processed documents yet. Upload a PDF to start the pipeline.</div>
    </section>
    <section class="panel match-results" *ngIf="matchResult"><div class="panel-header"><div><span class="step-number">05</span><h2>Latest matching results</h2></div><span class="muted-label">{{ matchResult.summary.processed }} PROCESSED</span></div><div class="match-summary"><div><b>{{ matchResult.summary.matched }}</b><span>Matched</span></div><div><b>{{ matchResult.summary.unmatched }}</b><span>Unmatched</span></div><div><b>{{ matchResult.summary.errors }}</b><span>Errors</span></div></div><article class="match-row" *ngFor="let item of matchResult.results"><div class="match-row-head"><strong>{{ item.document }}</strong><span [class.match-good]="item.status==='matched'">{{ item.status }}</span></div><p *ngIf="item.matched_case_number">Case: <b>{{ item.matched_case_number }}</b> · Confidence: {{ item.confidence | percent:'1.0-1' }}</p><p *ngIf="item.error" class="error-msg">{{ item.error }}</p><div class="field-pills" *ngIf="item.extracted_fields"><span *ngFor="let field of matchFieldEntries(item.extracted_fields)"><b>{{ field[0] }}:</b> {{ field[1] || '—' }}</span></div></article></section>
  </section>
  <section *ngIf="activeTab==='about'" class="about-workspace">
    <div class="about-hero">
      <div class="about-orb about-orb-one"></div><div class="about-orb about-orb-two"></div>
      <span class="about-kicker">INDIA AI HACKATHON · 2026</span>
      <div class="about-mark">AI<span>✦</span></div>
      <h1>Acceler-AI-te <span>2026</span></h1>
      <p class="about-tagline">Accelerating ideas with intelligent document workflows.</p>
      <p class="about-description">Intelligent Document Chunker brings document processing, AI-powered extraction, semantic embeddings, and case matching together in one streamlined workspace.</p>
    </div>
    <section class="panel about-team">
      <div class="panel-header"><div><span class="step-number">01</span><h2>Meet the developers</h2></div><span class="muted-label">BUILDING WITH AI</span></div>
      <div class="developer-grid">
        <article class="developer-card"><div class="developer-avatar avatar-ak">AK</div><div class="developer-name">Akshay Kulkarni</div><div class="developer-role">Developer</div><div class="developer-accent"></div></article>
        <article class="developer-card"><div class="developer-avatar avatar-pp">PP</div><div class="developer-name">Pankaj Pandey</div><div class="developer-role">Developer</div><div class="developer-accent"></div></article>
      </div>
    </section>
    <section class="about-footer-strip"><span class="about-footer-icon">✦</span><div><strong>India AI Hackathon — Acceler-AI-te 2026</strong><p>Ideas into impact through practical AI innovation.</p></div></section>
  </section>
  <ng-container *ngIf="activeTab==='chunk'">
  <div class="metrics-row"><div class="metric-card"><div class="metric-label">CURRENT DOCUMENT</div><div class="metric-value small-value">{{ file?.name || 'No document selected' }}</div><div class="metric-foot">{{ file ? formatSize(file.size) : 'Upload a file to get started' }}</div></div><div class="metric-card"><div class="metric-label">CHUNK COUNT</div><div class="metric-value">{{ result?.total_chunks ?? '—' }}</div><div class="metric-foot">{{ result ? 'Generated chunks' : 'Waiting for processing' }}</div></div><div class="metric-card"><div class="metric-label">STRATEGY</div><div class="metric-value strategy-value">{{ result?.config?.strategy || strategy }}</div><div class="metric-foot">{{ result?.recommendation ? 'Auto-selected recommendation' : 'Configurable chunking method' }}</div></div><div class="metric-card"><div class="metric-label">CONNECTION STATUS</div><div class="metric-value local-value">{{ healthStatus || 'OK' }}</div><div class="metric-foot"><span class="tiny-green-dot"></span>{{ healthStatus === '200' ? 'Connected' : 'Check API status' }}</div></div></div>
  <div class="workspace-grid"><section class="panel config-panel"><div class="panel-header"><div><span class="step-number">01</span><h2>Configure chunking</h2></div><span class="muted-label">SETTINGS</span></div>
  <label class="upload-zone" [class.has-file]="!!file" for="fileInput"><input id="fileInput" type="file" (change)="onFile($event)" accept=".pdf,.txt,.md,.csv,.xlsx,.xls,.docx,.json,.xml,.html,.py,.java,.js,.sql"/><span class="upload-symbol">↑</span><strong>{{ file?.name || 'Drop a document here' }}</strong><span>{{ file ? formatSize(file.size) + ' · Ready to process' : 'or click to browse files' }}</span><small>PDF · DOCX · TXT · MD · CSV · XLSX · JSON · XML · HTML · CODE</small></label>
  <div class="form-group"><label for="strategy">CHUNKING STRATEGY</label><select id="strategy" [(ngModel)]="strategy"><option value="auto">Auto — recommend best fit</option><option value="recursive">Recursive</option><option value="fixed">Fixed size</option><option value="semantic">Semantic</option><option value="sentence">Sentence</option><option value="paragraph">Paragraph</option><option value="table">Table-aware</option><option value="code">Code-aware</option><option value="parent_child">Parent-child</option><option value="sliding_window">Sliding window</option></select><p class="field-hint">Auto evaluates document structure and recommends a suitable strategy.</p></div>
  <div class="two-fields"><div class="form-group"><label for="chunkSize">CHUNK SIZE <b>{{ chunkSize | number }}</b></label><input id="chunkSize" type="range" min="100" max="10000" step="100" [(ngModel)]="chunkSize"/><div class="range-labels"><span>100 chars</span><span>10,000 chars</span></div></div><div class="form-group"><label for="overlap">OVERLAP <b>{{ overlap | number }}</b></label><input id="overlap" type="range" min="0" max="2000" step="25" [(ngModel)]="overlap"/><div class="range-labels"><span>0 chars</span><span>2,000 chars</span></div></div></div>
  <div class="info-strip"><span>ⓘ</span><p>Chunk size is measured in characters. Overlap must be no more than 50% of the chunk size.</p></div><div class="action-row"><button class="btn-secondary" [disabled]="!file || busy" (click)="run(true)">Preview chunks</button><button class="btn-primary" [disabled]="!file || busy" (click)="run(false)">{{ busy ? 'Processing…' : 'Process document' }} <span>→</span></button></div><p class="error-msg" *ngIf="error">{{ error }}</p><p class="success-msg" *ngIf="notice">{{ notice }}</p></section>
  <section class="panel results-panel"><div class="panel-header"><div><span class="step-number">02</span><h2>{{ result ? 'Chunk output' : 'Preview & output' }}</h2></div><div class="output-actions" *ngIf="result"><button class="small-btn" (click)="copyJson()">Copy JSON</button><button class="small-btn export-btn" (click)="downloadJson()">↓ Export</button></div></div>
  <div *ngIf="!result" class="empty-state"><div class="empty-illustration"><div class="doc-sheet"><i></i><i></i><i></i><i></i><span>✦</span></div><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div></div><h3>Your chunks will appear here</h3><p>Upload a document, preview the boundaries, then process the full file to inspect and export structured output.</p><div class="empty-features"><span>✓ Metadata included</span><span>✓ Character offsets</span><span>✓ JSON export</span></div></div>
  <div *ngIf="result" class="result-content"><div class="result-summary"><div><span class="result-kicker">DOCUMENT</span><strong>{{ result.document?.filename || file?.name }}</strong></div><div><span class="result-kicker">CHUNKS</span><strong>{{ result.total_chunks ?? result.chunks.length }}</strong></div><div><span class="result-kicker">MODE</span><strong>{{ isPreview ? 'Preview' : 'Full run' }}</strong></div></div><div class="recommendation" *ngIf="result.recommendation"><span class="recommendation-icon">✦</span><div><strong>Strategy recommendation</strong><p>{{ result.recommendation.rationale || ('Recommended strategy: ' + (result.recommendation.selected_strategy || strategy)) }}</p></div></div><div class="chunk-list"><article class="chunk-card" *ngFor="let chunk of result.chunks; let i = index"><div class="chunk-top"><span class="chunk-index">CHUNK {{ (i + 1).toString().padStart(2,'0') }}</span><span class="chunk-length">{{ chunk.text.length | number }} chars</span></div><pre>{{ chunk.text }}</pre><div class="chunk-meta"><span *ngFor="let item of metadataEntries(chunk.metadata) | slice:0:4"><b>{{ item[0] }}</b> {{ item[1] }}</span></div></article></div><div class="result-footer" *ngIf="result.warnings?.length"><span>ⓘ</span>{{ result.warnings?.join(' · ') }}</div></div></section></div>
  <footer class="page-footer"><span>Built for structured document workflows</span><span><i></i> CHUNKING API <b>OPERATIONAL</b></span></footer></ng-container></main>
</div>
` })
export class AppComponent {
  private readonly apiUrl = 'https://gp-intelligent-document-chunker.onrender.com';
  healthStatus = '';
  matchFiles: File[] = []; matchStrategy = 'auto'; matchChunkSize = 1000; matchBusy = false; matchError = ''; matchNotice = ''; matchResult: MatchResponse | null = null; matchDashboard: MatchDashboard | null = null;
  file: File | null = null; strategy = 'auto'; chunkSize = 1000; overlap = 150; busy = false; result: ApiResult | null = null; isPreview = false; error = ''; notice = ''; activeTab = 'chunk';
  get matchFilesLabel(): string { return this.matchFiles.map((f: File) => f.name).join(', '); }
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

  onMatchDocs(event: Event) { this.matchFiles = Array.from((event.target as HTMLInputElement).files || []); this.matchResult = null; this.matchError = ''; this.matchNotice = ''; }
  matchFieldEntries(fields: Record<string, unknown>): [string, string][] { return Object.entries(fields).map(([k,v]) => [k.replaceAll('_',' '), v == null ? '' : String(v)]); }
  distributionWidth(count: number): number { const max = Math.max(1, ...(this.matchDashboard?.chunk_distribution || []).map(x => x.count)); return Math.max(4, count / max * 100); }
  piePalette = ['#18a6a0', '#3978d4', '#8a69d4', '#e6a23c', '#e46d69', '#45a3d1', '#7c9b54', '#9aa7b7', '#cf78a8', '#5d6b82'];
  pieColor(index: number): string { return this.piePalette[index % this.piePalette.length]; }
  strategyPieGradient(): string {
    const items = this.matchDashboard?.chunk_distribution || [];
    const total = items.reduce((sum, item) => sum + item.count, 0);
    if (!total) return 'conic-gradient(#e8edf3 0deg 360deg)';
    let angle = 0;
    const stops = items.map((item, i) => { const start = angle; angle += item.count / total * 360; return `${this.pieColor(i)} ${start}deg ${angle}deg`; });
    return `conic-gradient(${stops.join(', ')})`;
  }
  statusCount(status: string): number {
    const docs = this.matchDashboard?.recent_documents || [];
    if (status === 'other') return docs.filter(d => !['matched','unmatched','error'].includes((d.status || '').toLowerCase())).length;
    return docs.filter(d => (d.status || '').toLowerCase() === status).length;
  }
  statusPieGradient(): string {
    const values = [this.statusCount('matched'), this.statusCount('unmatched'), this.statusCount('error'), this.statusCount('other')];
    const colors = ['#18a6a0', '#3978d4', '#e46d69', '#9aa7b7'];
    const total = values.reduce((a,b) => a+b, 0);
    if (!total) return 'conic-gradient(#e8edf3 0deg 360deg)';
    let angle = 0;
    const stops = values.map((v,i) => { const start=angle; angle += v/total*360; return `${colors[i]} ${start}deg ${angle}deg`; });
    return `conic-gradient(${stops.join(', ')})`;
  }
  loadMatchDashboard() {
    this.http.get<MatchDashboard>(`${this.apiUrl}/v1/match-engine/dashboard`).subscribe({
      next: data => this.matchDashboard = data,
      error: (e: HttpErrorResponse) => this.matchError = e.error?.detail || `Could not load Match Engine dashboard (${e.status || 'network error'}).`
    });
  }
  runMatchEngine() {
    if (!this.matchFiles.length) return;
    this.matchBusy = true; this.matchError = ''; this.matchNotice = '';
    const body = new FormData();
    this.matchFiles.forEach(f => body.append('documents', f));
    body.append('strategy', this.matchStrategy);
    body.append('chunk_size', String(this.matchChunkSize));
    body.append('overlap', '150');
    this.http.post<MatchResponse>(`${this.apiUrl}/v1/match-engine`, body).subscribe({
      next: data => {
        this.matchResult = data; this.matchBusy = false;
        this.matchNotice = `Finished: ${data.summary.matched} matched, ${data.summary.unmatched} unmatched, ${data.summary.errors} errors.`;
        this.matchFiles = [];
        this.loadMatchDashboard();
      },
      error: (e: HttpErrorResponse) => { this.matchBusy = false; this.matchError = e.error?.detail || `Match Engine failed (${e.status || 'network error'}). Check backend configuration.`; }
    });
  }
  metadataEntries(meta?: Record<string, unknown>): [string, string][] { return Object.entries(meta || {}).filter(([,v]) => v !== null && v !== undefined && typeof v !== 'object').map(([key, value]) => [key, String(value)]); }
  downloadJson() { if (!this.result) return; const blob = new Blob([JSON.stringify(this.result, null, 2)], {type:'application/json'}); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${this.file?.name || 'document'}.chunks.json`; a.click(); URL.revokeObjectURL(url); }
  copyJson() { if (!this.result) return; navigator.clipboard.writeText(JSON.stringify(this.result, null, 2)).then(() => this.notice = 'JSON copied to clipboard.').catch(() => this.error = 'Clipboard access was blocked by the browser.'); }
  checkHealth() { this.error = ''; this.http.get<unknown>(`${this.apiUrl}/health`).subscribe({ next: () => { this.healthStatus = '200'; this.notice = 'API connection is healthy.'; }, error: (e: HttpErrorResponse) => { this.healthStatus = String(e.status || 'ERR'); this.error = `API health check failed (${e.status || 'network error'}). Check backend URL and CORS configuration.`; } }); }
}
