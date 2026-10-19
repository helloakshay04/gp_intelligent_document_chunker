from pathlib import Path
import re
from collections import Counter
from .models import StrategyRecommendation

STRATEGIES = ["fixed", "recursive", "semantic", "sentence", "paragraph", "table", "code", "parent_child", "sliding_window"]

def analyze_content(filename: str, file_type: str, text: str, source_metadata: dict | None = None) -> dict:
    ext=Path(filename).suffix.lower(); lines=text.splitlines(); nonempty=[x for x in lines if x.strip()]
    table_lines=sum(bool(re.search(r"\|.+\|",x) or (x.count(",")>=2 and len(x)>8) or re.search(r"\s{2,}\S+\s{2,}\S+",x)) for x in nonempty)
    headings=sum(bool(re.match(r"^\s{0,3}(#{1,6}\s|\d+(?:\.\d+)*[.)]?\s+|<h[1-6]\b|<[^>]+\bid=)",x,re.I)) for x in nonempty)
    code_lines=sum(bool(re.match(r"\s*(def |class |async def |function |export |public |private |protected |SELECT\b|CREATE\b|INSERT\b|UPDATE\b|import |from )",x,re.I)) for x in nonempty)
    paragraphs=[p for p in re.split(r"\n\s*\n",text) if p.strip()]
    sentences=len(re.findall(r"[.!?](?:\s|$)",text)); words=len(re.findall(r"\b\w+\b",text))
    return {"extension":ext,"characters":len(text),"words":words,"lines":len(lines),"paragraphs":len(paragraphs),"sentences":sentences,
            "table_line_ratio":round(table_lines/max(1,len(nonempty)),3),"heading_count":headings,"code_declaration_count":code_lines,
            "markdown_table":bool(re.search(r"(?m)^\s*\|?\s*:?-{3,}:?\s*\|",text)),"html_structure":bool(re.search(r"(?is)<(table|article|section|h[1-6])\b",text)),
            "nested_table_signal":bool(re.search(r"(?is)<table\b.*?<table\b",text)) or bool((source_metadata or {}).get("nested_table_detected")),"html_table_rows":(source_metadata or {}).get("html_table_rows",0),"has_code_fence":"```" in text}

def _split_preview(text, strategy, size, overlap):
    # Import locally to avoid circular import.
    from .chunking import chunk_text
    from .models import ChunkingConfig
    return chunk_text(text, ChunkingConfig(chunk_size=size, overlap=overlap, strategy=strategy), strategy)

def _quality_score(text, chunks, strategy, signals):
    if not chunks: return 0.0
    lengths=[len(c["text"]) for c in chunks]; mean=sum(lengths)/len(lengths); utilization=min(1.0,mean/max(1,min(1000,max(lengths))))
    too_small=sum(n<min(120,mean*.25) for n in lengths)/len(lengths)
    boundary=0.0
    for c in chunks:
        t=c["text"].rstrip()
        if t.endswith((".","!","?",":",";","}",")","|")): boundary+=1
    boundary/=len(chunks)
    score=.45*(1-too_small)+.25*boundary+.30*min(1,mean/500)
    if strategy=="table": score += .20*signals["table_line_ratio"] + (.1 if signals["markdown_table"] or signals["html_structure"] else 0)
    if strategy=="code": score += min(.25,signals["code_declaration_count"]*.025)+(.08 if signals["has_code_fence"] else 0)
    if strategy=="paragraph": score += min(.2,signals["paragraphs"]/max(1,len(chunks))*.04)
    if strategy=="sentence": score += .08 if signals["sentences"]>2 else 0
    if strategy=="semantic": score += .06 if signals["paragraphs"]>1 and signals["sentences"]>2 else 0
    if strategy=="parent_child": score += .1 if signals["paragraphs"]>1 else 0
    if strategy=="sliding_window": score += .05 if len(chunks)>1 else 0
    if strategy=="fixed": score += .05
    if strategy=="recursive": score += .12
    return round(max(0,min(.99,score)),4)

def recommend_strategy(filename: str, file_type: str, text: str, *, chunk_size: int=1000, overlap: int=150, source_metadata: dict | None = None) -> StrategyRecommendation:
    signals=analyze_content(filename,file_type,text,source_metadata); ext=signals["extension"]
    candidates=STRATEGIES.copy()
    # Quality-aware candidate bake-off on a bounded representative sample; scores are structural proxies, not retrieval measurements.
    sample=text[:min(len(text), max(chunk_size*10, 5000))]
    scores={}
    for strategy in candidates:
        try: scores[strategy]=_quality_score(sample,_split_preview(sample,strategy,chunk_size,overlap),strategy,signals)
        except Exception: scores[strategy]=0.0
    priors={"table":signals["table_line_ratio"]*.65 + (.25 if ext in {".csv",".xlsx",".xls"} else 0),
            "code":min(.8,signals["code_declaration_count"]*.08)+(.35 if ext in {".py",".java",".js",".sql"} else 0),
            "paragraph":min(.35,signals["paragraphs"]*.015)+(.18 if ext in {".md",".docx"} else 0),
            "recursive":.18,"semantic":.10 if signals["paragraphs"]>1 else 0,"parent_child":.12 if signals["paragraphs"]>2 else 0,
            "sentence":.08 if signals["sentences"]>2 else 0,"fixed":.02,"sliding_window":.04}
    # Strong structure signals adjust candidate scores; content can override misleading extensions.
    for name,prior in priors.items(): scores[name]=round(min(.99,scores[name]+prior),4)
    if signals["markdown_table"] or signals["html_structure"] and signals["table_line_ratio"]>.15: scores["table"]=min(.99,scores["table"]+.12)
    if signals["has_code_fence"] or signals["code_declaration_count"]>=2: scores["code"]=min(.99,scores["code"]+.12)
    ranked=sorted(scores,key=scores.get,reverse=True); chosen=ranked[0]
    # Prevent noisy tiny-sample score fluctuations from choosing a weakly suitable structural mode.
    if ext in {".csv",".xlsx",".xls"} or signals["table_line_ratio"]>=.35 or signals["html_table_rows"]>0 or signals["nested_table_signal"]: chosen="table"
    elif ext in {".py",".java",".js",".sql"} or signals["code_declaration_count"]>=3: chosen="code"
    elif ext==".md" and signals["heading_count"]>0: chosen="paragraph" if scores["paragraph"]>=scores["recursive"]-.08 else "recursive"
    elif chosen not in scores: chosen="recursive"
    confidence=round(min(.97,max(.5,scores[chosen]-(scores[ranked[1]] if len(ranked)>1 else 0)*.15)),2)
    reasons={"table":"Table-like rows or structured tabular content were detected; rows and labels should stay together.","code":"Code declarations, fences, or a source-code extension indicate syntax-aware boundaries.",
             "paragraph":"Paragraphs/headings are prominent; keeping prose sections intact is preferred.","semantic":"Paragraph and sentence structure suggests boundary-aware semantic grouping.","parent_child":"The document has multiple sections; hierarchical child chunks can retain parent context.",
             "sentence":"Sentence boundaries are the strongest available natural-language units.","sliding_window":"Overlapping windows preserve continuity across longer unstructured content.","fixed":"Uniform windows are suitable for content with weak natural boundaries.","recursive":"General-purpose splitting balances paragraphs, lines, and size limits."}
    return StrategyRecommendation(strategy=chosen,reason=reasons[chosen],confidence=confidence,alternatives=[s for s in ranked if s!=chosen][:3],content_signals=signals,candidate_scores=scores)
