import re
from .models import ChunkingConfig

def _split_long_spans(text: str, size: int, overlap: int, offset: int=0) -> list[dict]:
    chunks=[]; start=0; n=len(text)
    while start<n:
        end=min(start+size,n)
        if end<n:
            floor=start+int(size*.55)
            candidates=[text.rfind(sep,floor,end) for sep in ("\n", ". ", "; ", " ")]
            candidate=max(candidates)
            if candidate>start: end=candidate+(1 if text[candidate:candidate+1] in ".;" else 0)
        raw=text[start:end]; left=len(raw)-len(raw.lstrip()); right=len(raw.rstrip()); piece=raw.strip()
        if piece: chunks.append({"text":piece,"start_char":offset+start+left,"end_char":offset+start+right})
        if end>=n: break
        start=max(start+1,end-overlap)
    return chunks

def _units(text: str, strategy: str) -> list[tuple[str,int,int]]:
    if strategy=="sentence": pattern=r"(?<=[.!?])\s+"
    elif strategy=="paragraph": pattern=r"\n\s*\n"
    elif strategy in {"recursive","semantic","parent_child"}: pattern=r"\n\s*\n|(?=^#{1,6}\s)|(?=^\d+(?:\.\d+)*[.)]?\s+)"
    elif strategy=="table":
        # Rows are atomic when possible, including Markdown pipe rows and flattened HTML table rows.
        pattern=r"\n(?=(?:\|.*\||\[TABLE(?:\]|\s)|[^\n]*\s\|\s[^\n]*))"
    elif strategy=="code": pattern=r"\n(?=(?:\s*(?:async\s+def|def|class|function|export|public|private|protected|SELECT|CREATE|INSERT|UPDATE|DELETE|WITH)\b))"
    else: return [(text,0,len(text))]
    out=[]; last=0
    for m in re.finditer(pattern,text,flags=re.I|re.M):
        end=m.start(); part=text[last:end]
        if part.strip():
            l=len(part)-len(part.lstrip()); r=len(part.rstrip()); out.append((part.strip(),last+l,last+r))
        last=m.end()
    part=text[last:]
    if part.strip():
        l=len(part)-len(part.lstrip()); r=len(part.rstrip()); out.append((part.strip(),last+l,last+r))
    return out

def chunk_text(text: str, config: ChunkingConfig, strategy: str | None=None) -> list[dict]:
    chosen=strategy or config.strategy
    if chosen=="auto": chosen="recursive"
    if not text or not text.strip(): return []
    if chosen in {"fixed","sliding_window"}:
        overlap=config.overlap if chosen=="sliding_window" else config.overlap
        return _split_long_spans(text,config.chunk_size,overlap)
    if chosen=="parent_child":
        # Parent units are retained as metadata on each child. Children remain bounded and independently retrievable.
        parents=_units(text,"paragraph") or [(text,0,len(text))]; out=[]; parent_no=0
        for parent,pstart,pend in parents:
            parent_limit=max(config.chunk_size*2,2000)
            parent_blocks=[(parent,pstart,pend)] if len(parent)<=parent_limit else [(b["text"],b["start_char"],b["end_char"]) for b in _split_long_spans(parent,parent_limit,0,pstart)]
            for parent_block,block_start,block_end in parent_blocks:
                parent_id=f"parent_{parent_no:05d}"; child_size=max(100,min(config.chunk_size,max(100,int(config.chunk_size*.55))))
                for child in _split_long_spans(parent_block,child_size,min(config.overlap,child_size//2),block_start):
                    child.update({"chunk_type":"child","parent_id":parent_id,"parent_text":parent_block,"parent_start_char":block_start,"parent_end_char":block_end})
                    out.append(child)
                # Always emit parent context, even for very long documents (large parents are split into blocks above).
                out.append({"text":parent_block,"start_char":block_start,"end_char":block_end,"chunk_type":"parent","parent_id":parent_id,"parent_text":parent_block,"parent_start_char":block_start,"parent_end_char":block_end})
                parent_no+=1
        out.sort(key=lambda x:(x["start_char"],0 if x.get("chunk_type")=="parent" else 1))
        return out
    units=_units(text,chosen); out=[]; current=""; current_start=0; current_end=0
    for unit,start,end in units:
        if len(unit)>config.chunk_size:
            if current: out.append({"text":current,"start_char":current_start,"end_char":current_end}); current=""
            out.extend(_split_long_spans(unit,config.chunk_size,config.overlap,start)); continue
        if not current: current=unit; current_start=start; current_end=end
        elif len(current)+2+len(unit)<=config.chunk_size:
            current += "\n\n"+unit; current_end=end
        else:
            out.append({"text":current,"start_char":current_start,"end_char":current_end})
            tail=current[-config.overlap:] if config.overlap else ""
            current=(tail+"\n\n"+unit).strip() if tail else unit
            current_start=max(0,end-len(current)); current_end=end
            if len(current)>config.chunk_size:
                parts=_split_long_spans(current,config.chunk_size,config.overlap,current_start); out.extend(parts[:-1]); current=parts[-1]["text"] if parts else ""; current_start=parts[-1]["start_char"] if parts else end; current_end=parts[-1]["end_char"] if parts else end
    if current: out.append({"text":current,"start_char":current_start,"end_char":current_end})
    normalized=[]
    for item in out:
        if len(item["text"])<=config.chunk_size: normalized.append(item)
        else: normalized.extend(_split_long_spans(item["text"],config.chunk_size,config.overlap,item["start_char"]))
    return normalized
