from pathlib import Path
import time, uuid
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
from chunker_sdk import DocumentChunker, ChunkingConfig, __version__
from chunker_sdk.extractors import SUPPORTED_EXTENSIONS
from chunker_sdk.telemetry import span, get_metrics, prometheus_metrics, logger, record_call
BASE_DIR=Path(__file__).resolve().parents[1]; UI_DIR=BASE_DIR/"ui"; engine=DocumentChunker()
app = FastAPI(
    title="Global Payments Intelligent Document Chunker",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.mount("/ui",StaticFiles(directory=UI_DIR),name="ui")
@app.middleware("http")
async def request_observability(request:Request,call_next):
    trace_id=request.headers.get("x-trace-id") or uuid.uuid4().hex[:16]; request.state.trace_id=trace_id; started=time.perf_counter()
    try:
        with span("http_request",trace_id,method=request.method,path=request.url.path): response=await call_next(request)
        response.headers["X-Trace-Id"]=trace_id; response.headers["X-Process-Time-Ms"]=str(round((time.perf_counter()-started)*1000,3)); return response
    except Exception as exc:
        logger.error("http.request.error",extra={"trace_id":trace_id,"span":"http_request","error_type":type(exc).__name__}); raise
@app.get("/health")
def health():return {"status":"ok","sdk_version":__version__}
@app.get("/metrics")
def metrics():return get_metrics()
@app.get("/metrics/prometheus",response_class=PlainTextResponse)
def metrics_prometheus():return prometheus_metrics()
@app.get("/v1/config")
def config():return {"sdk_version":__version__,"supported_extensions":sorted(SUPPORTED_EXTENSIONS),"bounds":{"chunk_size":{"min":100,"max":10000,"default":1000},"overlap":{"min":0,"max":2000,"default":150,"max_percent_of_chunk_size":50},"preview_count":{"min":5,"max":10,"default":8}},"strategies":["auto","fixed","recursive","semantic","sentence","paragraph","table","code","parent_child","sliding_window"]}
def _cfg(strategy,chunk_size,overlap,preview_count=8):
    aliases={"table_aware":"table","code_aware":"code","sliding-window":"sliding_window","parent-child":"parent_child"}
    strategy=aliases.get(strategy,strategy)
    return ChunkingConfig(strategy=strategy,chunk_size=chunk_size,overlap=overlap,preview_count=preview_count)
@app.post("/v1/preview")
async def preview_document(request:Request,file:UploadFile=File(...),strategy:str=Form("auto"),chunk_size:int=Form(1000),overlap:int=Form(150),preview_count:int=Form(8)):
    if not file.filename:raise HTTPException(status_code=400,detail="Filename is required.")
    content=await file.read()
    try:
        result=engine.preview(file.filename,content,_cfg(strategy,chunk_size,overlap,preview_count),trace_id=request.state.trace_id).model_dump(mode="json")
        result["chunks"]=result.pop("preview_chunks"); result["total_chunks"]=result.pop("estimated_total_chunks"); result["is_preview"]=True
        return result
    except (ValueError,ValidationError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=422,detail=f"Preview failed ({type(exc).__name__}). Check file format and logs using the trace ID.") from exc
    finally:await file.close()
@app.post("/v1/chunk")
async def chunk_document(request:Request,file:UploadFile=File(...),strategy:str=Form("auto"),chunk_size:int=Form(1000),overlap:int=Form(150)):
    if not file.filename:raise HTTPException(status_code=400,detail="Filename is required.")
    content=await file.read()
    try:return engine.process(file.filename,content,_cfg(strategy,chunk_size,overlap),trace_id=request.state.trace_id).model_dump(mode="json")
    except (ValueError,ValidationError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc
    except Exception as exc:raise HTTPException(status_code=422,detail=f"Processing failed ({type(exc).__name__}). Check file format and logs using the trace ID.") from exc
    finally:await file.close()
class TextChunkRequest(BaseModel):
    text:str=Field(min_length=1); filename:str="inline.txt"; strategy:str="auto"; chunk_size:int=Field(default=1000,ge=100,le=10000); overlap:int=Field(default=150,ge=0,le=2000)
@app.post("/v1/chunk-text")
def chunk_text_endpoint(request:TextChunkRequest):
    try:return engine.process(request.filename,request.text.encode(),_cfg(request.strategy,request.chunk_size,request.overlap)).model_dump(mode="json")
    except (ValueError,ValidationError) as exc:raise HTTPException(status_code=400,detail=str(exc)) from exc

