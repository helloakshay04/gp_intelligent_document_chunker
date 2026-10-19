from pathlib import Path
from uuid import uuid4
import hashlib, time
from . import __version__
from .models import Chunk, ChunkingConfig, ChunkingResult, ChunkPreview, DocumentInfo
from .extractors import extract_document
from .strategies import recommend_strategy
from .chunking import chunk_text
from .telemetry import span, logger, record_call

class DocumentChunker:
    """Reusable SDK. Preview is bounded; process generates the complete chunk set."""
    def __init__(self, *, min_chunk_size=100, max_chunk_size=10000, max_file_bytes=25*1024*1024):
        self.min_chunk_size,self.max_chunk_size,self.max_file_bytes=min_chunk_size,max_chunk_size,max_file_bytes
    def _prepare(self,filename,content,config,trace_id=None):
        if not isinstance(content,(bytes,bytearray)): raise ValueError("content must be bytes")
        if not content: raise ValueError("Uploaded file is empty.")
        if len(content)>self.max_file_bytes: raise ValueError(f"File exceeds maximum allowed size of {self.max_file_bytes} bytes.")
        config=config if isinstance(config,ChunkingConfig) else ChunkingConfig(**(config or {}))
        if not self.min_chunk_size<=config.chunk_size<=self.max_chunk_size: raise ValueError(f"chunk_size must be between {self.min_chunk_size} and {self.max_chunk_size}.")
        with span("extract_document",trace_id,document_name=Path(filename).name,file_bytes=len(content)) as sp:
            extracted=extract_document(filename,bytes(content))
        doc_id=uuid4().hex; text=extracted["text"]
        with span("analyze_and_recommend",sp["trace_id"],document_name=Path(filename).name) as _:
            rec=recommend_strategy(filename,extracted["file_type"],text,chunk_size=config.chunk_size,overlap=config.overlap,source_metadata=extracted.get("structure_signals",{}))
        strategy=rec.strategy if config.strategy=="auto" else config.strategy
        actual=config.model_copy(update={"strategy":strategy})
        info=DocumentInfo(document_id=doc_id,filename=Path(filename).name,extension=extracted["extension"],file_type=extracted["file_type"],size_bytes=len(content),content_type=extracted["content_type"],page_count=extracted["page_count"],sheet_names=extracted["sheet_names"],warnings=extracted["warnings"])
        return extracted,doc_id,rec,actual,info,sp["trace_id"]
    def _chunks(self, extracted, doc_id, rec, cfg, info, *, limit=None, trace_id=None):
        text=extracted["text"]
        with span("chunk_document",trace_id,strategy=cfg.strategy,document_name=info.filename) as _:
            raw=chunk_text(text,cfg,cfg.strategy)
        if limit is not None: raw=raw[:limit]
        chunks=[]
        for idx,item in enumerate(raw):
            start=item.get("start_char",0); end=item.get("end_char",start+len(item["text"])); sources=[]
            for section in extracted["sections"]:
                meta=section.get("metadata",{}); ss=meta.get("start_char",0); se=meta.get("end_char",0)
                if ss<end and se>start:
                    clean={k:v for k,v in meta.items() if k not in {"start_char","end_char"}}
                    if clean and clean not in sources:sources.append(clean)
            primary=sources[0] if sources else {}
            metadata={"sourceDocument":info.filename,"filename":info.filename,"extension":info.extension,"file_type":info.file_type,
                "pageNumber":primary.get("page_number"),"section":primary.get("section"),"sourceMetadata":sources[:10],"sources":sources[:10],
                "strategy":cfg.strategy,"chunk_size_limit":cfg.chunk_size,"overlap":cfg.overlap,"sdk_version":__version__,
                "startChar":start,"endChar":end,"contentHash":hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                "chunkType":item.get("chunk_type","standard")}
            if "row_number" in primary:metadata["rowNumber"]=primary["row_number"]
            if "sheet_name" in primary:metadata["sheetName"]=primary["sheet_name"]
            if "paragraph_number" in primary:metadata["paragraphNumber"]=primary["paragraph_number"]
            if "table" in primary:metadata["tableNumber"]=primary["table"]
            if "parent_id" in item:metadata["parentId"]=f"{doc_id}_{item['parent_id']}"
            if "parent_text" in item:metadata["parentContext"]=item["parent_text"]
            if "parent_start_char" in item:metadata["parentStartChar"]=item["parent_start_char"]
            if "parent_end_char" in item:metadata["parentEndChar"]=item["parent_end_char"]
            chunks.append(Chunk(chunk_id=f"{doc_id}_{idx:05d}",document_id=doc_id,index=idx,text=item["text"],char_count=len(item["text"]),metadata=metadata))
        return chunks,raw
    def preview(self,filename:str,content:bytes,config:ChunkingConfig|dict|None=None,*,trace_id:str|None=None)->ChunkPreview:
        started=time.perf_counter(); trace_id=None; error=False
        try:
            extracted,doc_id,rec,cfg,info,trace_id=self._prepare(filename,content,config,trace_id)
            text=extracted["text"]; sample=text[:min(len(text),max(cfg.chunk_size*12,6000))]
            # Preview uses a representative prefix only. It does not materialize the full chunk set.
            sample_extracted={**extracted,"text":sample,"sections":[s for s in extracted["sections"] if s["metadata"].get("start_char",0)<len(sample)]}
            preview_cfg=cfg.model_copy(update={"strategy":cfg.strategy})
            chunks,raw=self._chunks(sample_extracted,doc_id,rec,preview_cfg,info,limit=cfg.preview_count,trace_id=trace_id)
            sample_count=len(chunk_text(sample,preview_cfg,cfg.strategy)); est=max(sample_count,round(sample_count*len(text)/max(1,len(sample)))) if text else 0
            warnings=list(extracted["warnings"])
            if len(text)>len(sample):warnings.append("Preview is sampled from the beginning of the document; full processing will generate all chunks.")
            if cfg.strategy=="parent_child":warnings.append("Parent-child preview contains both parent-context and child chunks; full output retains both.")
            elapsed=(time.perf_counter()-started)*1000; record_call(elapsed,len(content),len(chunks),preview=True)
            return ChunkPreview(sdk_version=__version__,document=info,recommendation=rec,config=cfg,total_characters=len(text),estimated_total_chunks=est,preview_chunks=chunks,warnings=warnings,metrics={"duration_ms":round(elapsed,3),"preview_chunk_count":len(chunks),"sample_characters":len(sample)},trace={"trace_id":trace_id,"spans":["extract_document","analyze_and_recommend","chunk_document"]})
        except Exception:
            error=True; raise
        finally:
            if error:record_call((time.perf_counter()-started)*1000,len(content or b""),error=True,preview=True)
    def process(self,filename:str,content:bytes,config:ChunkingConfig|dict|None=None,*,trace_id:str|None=None)->ChunkingResult:
        started=time.perf_counter(); error=False
        try:
            extracted,doc_id,rec,cfg,info,trace_id=self._prepare(filename,content,config,trace_id)
            chunks,_=self._chunks(extracted,doc_id,rec,cfg,info,trace_id=trace_id)
            warnings=list(extracted["warnings"])
            if not extracted["text"].strip():warnings.append("No extractable text was found. Image-only PDFs may require OCR.")
            elapsed=(time.perf_counter()-started)*1000; record_call(elapsed,len(content),len(chunks))
            logger.info("document.processed",extra={"trace_id":trace_id,"document_name":info.filename,"strategy":cfg.strategy,"chunk_count":len(chunks),"file_bytes":len(content),"duration_ms":round(elapsed,3)})
            return ChunkingResult(sdk_version=__version__,document=info,recommendation=rec,config=cfg,extracted_text_preview=extracted["text"][:3000],total_characters=len(extracted["text"]),total_chunks=len(chunks),chunks=chunks,warnings=warnings,metrics={"duration_ms":round(elapsed,3),"input_bytes":len(content),"chunk_count":len(chunks)},trace={"trace_id":trace_id,"spans":["extract_document","analyze_and_recommend","chunk_document"]})
        except Exception:
            error=True; raise
        finally:
            if error:record_call((time.perf_counter()-started)*1000,len(content or b""),error=True)
