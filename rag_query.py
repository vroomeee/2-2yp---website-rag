#!/usr/bin/env python3
import os, json, time, pickle, re, argparse
import numpy as np, faiss
from openai import OpenAI

STORE_DIR="rag_store"
EMBED_MODEL="text-embedding-3-large"
GEN_MODEL="gpt-5.2"
TOP_K_RETRIEVE=60
TOP_K_FINAL=8
RRF_K=60
RERANK=True
SHOW_DOCS=True
DOC_CHAR_LIMIT=1200
RERANK_CHAR_LIMIT=1200
MAX_ROUNDS=3
LOG_DIR="logs"
RELAX_CONTEXT=False
MAX_QUERY_EXPANSIONS=10
PRE_RERANK_TOP_K=64
TITLE_MATCH_BONUS=0.5
NOT_FOUND_MSG=(
    "제공된 데이터로는 답을 확정하기 어렵습니다. "
    "더 가져오고 싶어도 과도한 확장은 RAG의 본질적 한계와 맞닿아 있어, "
    "현 시점에선 확답이 어렵습니다."
)

client=OpenAI()
_embed_cache={}

FILTER_RE=re.compile(r"\b(title|link|row_id|chunk_id):(?:(\"[^\"]+\")|(\S+))",re.IGNORECASE)
WORD_RE=re.compile(r"[A-Za-z0-9가-힣]+")
META_ONLY_RE=re.compile(r"(?:^|\s)~(\S+)")


def load_store(store_dir):
    index=faiss.read_index(os.path.join(store_dir,"index.faiss"))
    summary_path=os.path.join(store_dir,"index_summary.faiss")
    title_path=os.path.join(store_dir,"index_title.faiss")
    index_sum=faiss.read_index(summary_path) if os.path.exists(summary_path) else None
    index_title=faiss.read_index(title_path) if os.path.exists(title_path) else None
    with open(os.path.join(store_dir,"meta.jsonl"),"r",encoding="utf-8") as f:
        metas=[json.loads(l) for l in f if l.strip()]
    bm25_path=os.path.join(store_dir,"bm25.pkl")
    bm25_title_path=os.path.join(store_dir,"bm25_title.pkl")
    bm25=None
    bm25_title=None
    if os.path.exists(bm25_path):
        with open(bm25_path,"rb") as f:
            bm25=pickle.load(f)
    if os.path.exists(bm25_title_path):
        with open(bm25_title_path,"rb") as f:
            bm25_title=pickle.load(f)
    return index,index_sum,index_title,metas,bm25,bm25_title


def embed_many(queries):
    missing=[q for q in queries if q not in _embed_cache]
    if missing:
        resp=client.embeddings.create(model=EMBED_MODEL,input=missing)
        for q,d in zip(missing,resp.data):
            _embed_cache[q]=np.array(d.embedding,dtype=np.float32)
    vecs=[_embed_cache[q] for q in queries]
    arr=np.array(vecs,dtype=np.float32)
    faiss.normalize_L2(arr)
    return arr


def tokenize(t):
    return [m.group(0).lower() for m in WORD_RE.finditer(t)]


def classify_query(q):
    prompt=(
        "다음 질문을 다음 중 하나로 분류하세요: definition, comparison, multi-hop, list, other. "
        "라벨만 반환하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {q}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        label=resp.output_text.strip().lower()
        if label in {"definition","comparison","multi-hop","list","other"}:
            return label
    except Exception:
        pass
    return "other"


def decompose_query(q,mode):
    if mode not in {"comparison","multi-hop","list"}:
        return []
    prompt=(
        "질문을 2-4개의 집중된 하위 질문으로 분해하세요. 각 하위 질문은 독립적으로 "
        "답할 수 있어야 합니다. 한 줄에 하나씩, 번호 없이 반환하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {q}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        return [l.strip().lstrip("--").strip() for l in resp.output_text.splitlines() if l.strip()]
    except Exception:
        return []


def step_back_query(q):
    prompt=(
        "배경 정보를 찾기 위해 질문을 더 상위의 일반적인 수준으로 다시 작성하세요. "
        "한 줄만 반환하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {q}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        return resp.output_text.strip()
    except Exception:
        return ""


def multi_query(q):
    prompt=(
        "질문에 답할 수 있는 구절을 찾기 위해 짧은 검색 질의 3개를 생성하세요. "
        "한 줄에 하나씩, 번호 없이 반환하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {q}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        return [l.strip().lstrip("--").strip() for l in resp.output_text.splitlines() if l.strip()]
    except Exception:
        return []


def hyde_query(q):
    prompt=(
        "질문에 대한 그럴듯한 짧은 답을 작성하세요. 3문장 이내로 유지하세요. "
        "이 답변은 검색용입니다.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {q}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        return resp.output_text.strip()
    except Exception:
        return ""


def route_weights(mode):
    if mode=="definition":
        return {"full":0.8,"sum":1.4,"title":1.0,"bm25":1.0}
    if mode=="list":
        return {"full":1.0,"sum":1.2,"title":0.8,"bm25":1.0}
    if mode=="comparison":
        return {"full":1.3,"sum":0.8,"title":0.8,"bm25":1.2}
    if mode=="multi-hop":
        return {"full":1.4,"sum":0.8,"title":0.8,"bm25":1.2}
    return {"full":1.0,"sum":1.0,"title":1.0,"bm25":1.0}


def domain_expansions(q,mode):
    ex=[]
    if "조선왕조실록" not in q:
        ex.append(f"조선왕조실록 {q}")
    if "수정실록" in q or "편찬" in q or "실록" in q:
        ex.append(f"{q} 편찬 주체 사견")
    if "노론" in q or "소론" in q:
        ex.append(f"{q} 당파 갈등 사건")
    if mode=="comparison" or "비교" in q:
        ex.append(f"{q} 차이점")
        ex.append(f"{q} 서로 다른 기록")
    if "기사" in q:
        ex.append(f"{q} 기록")
    return ex


def build_queries(q,mode,extra_hint=""):
    queries=[q]
    subqs=decompose_query(q,mode)
    queries.extend([s for s in subqs if s and s.lower()!=q.lower()])
    sb=step_back_query(q)
    if sb and sb.lower()!=q.lower():
        queries.append(sb)
    queries.extend([x for x in multi_query(q) if x])
    h=hyde_query(q)
    if h:
        queries.append(h)
    if extra_hint:
        queries.append(extra_hint)
    queries.extend(domain_expansions(q,mode))
    seen=set()
    out=[]
    for s in queries:
        key=s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out[:MAX_QUERY_EXPANSIONS]


def parse_filters(q):
    filters={}
    def _clean(v):
        return v.strip().strip('"')
    for m in FILTER_RE.finditer(q):
        key=m.group(1).lower()
        val=m.group(2) or m.group(3) or ""
        if val:
            filters.setdefault(key,[]).append(_clean(val))
    q_clean=FILTER_RE.sub("",q).strip()
    return q_clean,filters


def parse_meta_only(q):
    hits=META_ONLY_RE.findall(q)
    if not hits:
        return q,False
    q_clean=META_ONLY_RE.sub(" ",q).replace("~"," ")
    q_clean=" ".join(q_clean.split())
    return q_clean,True


def filter_doc_ids(metas,filters):
    if not filters:
        return None
    allowed=[]
    for i,m in enumerate(metas):
        ok=True
        if "row_id" in filters:
            if str(m.get("row_id")) not in set(filters["row_id"]):
                ok=False
        if "chunk_id" in filters:
            if str(m.get("chunk_id")) not in set(filters["chunk_id"]):
                ok=False
        if "title" in filters:
            title=(m.get("title") or "").lower()
            if not any(f.lower() in title for f in filters["title"]):
                ok=False
        if "link" in filters:
            link=(m.get("link") or "").lower()
            if not any(f.lower() in link for f in filters["link"]):
                ok=False
        if ok:
            allowed.append(i)
    return set(allowed)


def bm25_search(query,bm25,top_k,allowed=None):
    if not bm25:
        return []
    postings=bm25["postings"]
    doc_len=bm25["doc_len"]
    avgdl=bm25["avgdl"]
    k1=bm25["k1"]
    b=bm25["b"]
    if not doc_len or avgdl==0:
        return []
    N=len(doc_len)
    scores={}
    terms=tokenize(query)
    for t in terms:
        plist=postings.get(t)
        if not plist:
            continue
        df=len(plist)
        idf=max(0.0, np.log((N-df+0.5)/(df+0.5)+1.0))
        for doc_id,tf in plist:
            if allowed is not None and doc_id not in allowed:
                continue
            denom=tf + k1*(1-b + b*(doc_len[doc_id]/avgdl))
            score=idf * (tf*(k1+1)) / denom
            scores[doc_id]=scores.get(doc_id,0.0)+score
    ranked=sorted(scores.items(),key=lambda x:x[1],reverse=True)
    return [doc_id for doc_id,_ in ranked[:top_k]]


def bm25_scores(query,bm25,allowed=None):
    if not bm25:
        return {}
    postings=bm25["postings"]
    doc_len=bm25["doc_len"]
    avgdl=bm25["avgdl"]
    k1=bm25["k1"]
    b=bm25["b"]
    if not doc_len or avgdl==0:
        return {}
    N=len(doc_len)
    scores={}
    terms=tokenize(query)
    for t in terms:
        plist=postings.get(t)
        if not plist:
            continue
        df=len(plist)
        idf=max(0.0, np.log((N-df+0.5)/(df+0.5)+1.0))
        for doc_id,tf in plist:
            if allowed is not None and doc_id not in allowed:
                continue
            denom=tf + k1*(1-b + b*(doc_len[doc_id]/avgdl))
            score=idf * (tf*(k1+1)) / denom
            scores[doc_id]=scores.get(doc_id,0.0)+score
    return scores


def rrf_search_multi(indices,bm25,queries,top_k,weights,allowed=None):
    scores={}
    sim_scores={}
    if queries:
        emb=embed_many(queries)
    for name,idx in indices.items():
        if idx is None:
            continue
        D,I=idx.search(emb,top_k)
        w=weights.get(name,1.0)
        for qi in range(I.shape[0]):
            for rank,doc_id in enumerate(I[qi]):
                if allowed is not None and doc_id not in allowed:
                    continue
                scores[doc_id]=scores.get(doc_id,0.0)+w/(RRF_K+rank+1)
                sim_scores[doc_id]=max(sim_scores.get(doc_id,-1.0),D[qi][rank])
    if bm25 is not None:
        w=weights.get("bm25",1.0)
        for q in queries:
            for rank,doc_id in enumerate(bm25_search(q,bm25,top_k,allowed=allowed)):
                scores[doc_id]=scores.get(doc_id,0.0)+w/(RRF_K+rank+1)
    ranked=sorted(scores.items(),key=lambda x:x[1],reverse=True)
    cand=[doc_id for doc_id,_ in ranked[:max(top_k,TOP_K_FINAL*12)]]
    return cand,scores,sim_scores


def lexical_prerank(query,metas,cand,bm25,top_k):
    if not cand:
        return cand
    allowed=set(cand)
    bm25_sc=bm25_scores(query,bm25,allowed=allowed)
    q_terms=set(tokenize(query))
    scored=[]
    for doc_id in cand:
        title=(metas[doc_id].get("title") or "")
        title_terms=set(tokenize(title))
        title_hits=len(q_terms & title_terms)
        score=bm25_sc.get(doc_id,0.0) + (title_hits*TITLE_MATCH_BONUS)
        scored.append((doc_id,score))
    scored.sort(key=lambda x:x[1],reverse=True)
    return [doc_id for doc_id,_ in scored[:top_k]]


def parse_json(text):
    start=text.find("{")
    end=text.rfind("}")
    if start==-1 or end==-1 or end<=start:
        return {}
    try:
        data=json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data,dict) else {}


def parse_json_list(text):
    start=text.find("[")
    end=text.rfind("]")
    if start==-1 or end==-1 or end<=start:
        return []
    try:
        data=json.loads(text[start:end+1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data,list):
        return []
    out=[]
    for x in data:
        try:
            out.append(int(x))
        except (TypeError,ValueError):
            continue
    return out


def rerank(query,metas,cand):
    if not RERANK or not cand:
        return cand[:TOP_K_FINAL]
    items=[]
    for idx in cand:
        m=metas[idx]
        items.append({
            "id":int(idx),
            "title":m.get("title",""),
            "text":m.get("text","")[:RERANK_CHAR_LIMIT],
        })
    prompt=(
        "당신은 엄격한 재랭커입니다. 질문과 문서 목록이 주어지면, 관련도 내림차순으로 "
        "가장 관련 있는 문서 id의 JSON 배열을 반환하세요. "
        f"최대 {TOP_K_FINAL}개의 id만 반환하고 JSON 배열만 출력하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {query}\n\n문서:\n{json.dumps(items,ensure_ascii=False)}"
    )
    ids=[]
    for _ in range(2):
        try:
            resp=client.responses.create(model=GEN_MODEL,input=prompt)
            ids=parse_json_list(resp.output_text)
        except Exception:
            ids=[]
        if ids:
            break
    if not ids:
        return cand[:TOP_K_FINAL]
    allowed=set(cand)
    out=[i for i in ids if i in allowed]
    return out[:TOP_K_FINAL] if out else cand[:TOP_K_FINAL]


def answer_or_request(q,ctx,allow_more=True,relax_context=False,mode="other"):
    schema=(
        "JSON만 반환하세요. 하나의 action을 선택하세요:\n"
        "1) {\"action\":\"answer\",\"answer\":\"...\",\"confidence\":0-1}\n"
        "2) {\"action\":\"search_more\",\"query\":\"...\",\"reason\":\"...\"}\n"
        "3) {\"action\":\"need_config\",\"message\":\"...\"}\n"
        "4) (답변일 때만) \"evidence_found\": [\"...\"], \"evidence_missing\": [\"...\"]\n"
    )
    guidance="" if allow_more else f"추가 검색을 요청할 수 없습니다. 답하거나 \"{NOT_FOUND_MSG}\"라고 하세요.\n"
    relax=(
        "문맥에 없는 내용은 추정임을 명확히 표시하고, "
        "문맥 근거가 있는 부분만 [1], [2]처럼 인라인 인용하세요. "
        "문맥 밖 정보에는 인용을 붙이지 마세요.\n"
    ) if relax_context else ""
    compare=(
        "비교 질문이면 2열 표 형식으로 답하세요. 질문에 나온 비교 대상을 각 열 제목으로 쓰고, "
        "각 셀에 근거를 요약하세요.\n"
    ) if mode=="comparison" else ""
    base_instruction="문맥만 사용하세요." if not relax_context else "문맥을 우선 사용하세요."
    prompt=(
        f"당신은 검색 증강 어시스턴트입니다. {base_instruction} "
        "근거는 [1], [2]처럼 본문에 인라인으로 표시하세요. "
        f"문맥에 답이 없으면 \"{NOT_FOUND_MSG}\"라고 하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n"
        f"{compare}{relax}{guidance}{schema}\n문맥:\n{''.join(ctx)}\n\n질문: {q}"
    )
    resp=client.responses.create(model=GEN_MODEL,input=prompt)
    data=parse_json(resp.output_text)
    return data


def verify_answer(q,ctx,answer):
    prompt=(
        "답변이 문맥에 의해 충분히 뒷받침되는지 확인하세요. "
        "JSON으로 반환: {\"supported\": true/false, \"missing\": \"...\"}.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"질문: {q}\n\n문맥:\n{''.join(ctx)}\n\n답변: {answer}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        data=parse_json(resp.output_text)
        supported=bool(data.get("supported",False))
        missing=str(data.get("missing","")).strip()
        return supported,missing
    except Exception:
        return True,""


def refine_query(q,missing):
    if not missing:
        return ""
    prompt=(
        "부족한 정보를 겨냥하도록 질문을 다시 작성하세요. "
        "개선된 단일 질의를 반환하세요.\n"
        "이 질문은 조선왕조실록에 관한 검색/질의입니다.\n\n"
        f"원본 질문: {q}\n부족한 정보: {missing}"
    )
    try:
        resp=client.responses.create(model=GEN_MODEL,input=prompt)
        return resp.output_text.strip()
    except Exception:
        return ""


def log_event(store_dir,payload):
    os.makedirs(os.path.join(store_dir,LOG_DIR),exist_ok=True)
    path=os.path.join(store_dir,LOG_DIR,"query_log.jsonl")
    payload["ts"]=time.time()
    with open(path,"a",encoding="utf-8") as f:
        f.write(json.dumps(payload,ensure_ascii=False)+"\n")


def format_meta(m):
    parts=[]
    if m.get("king"):
        parts.append(f"왕:{m['king']}")
    date=[]
    if m.get("year"):
        date.append(f"{m['year']}년")
    if m.get("month"):
        date.append(f"{m['month']}월")
    if m.get("day"):
        date.append(f"{m['day']}일")
    if date:
        parts.append(" ".join(date))
    if m.get("book"):
        parts.append(f"책/권:{m['book']}")
    if m.get("article"):
        parts.append(f"기사:{m['article']}")
    return " / ".join(parts)


def build_evidence_block(resp):
    found=resp.get("evidence_found")
    missing=resp.get("evidence_missing")
    if not found and not missing:
        return ""
    def _join(x):
        if isinstance(x,list):
            return ", ".join([str(i) for i in x if str(i).strip()]) or "-"
        return str(x).strip() or "-"
    return (
        "\n\n증거 체크리스트:\n"
        f"- 근거 있음: {_join(found)}\n"
        f"- 근거 부족: {_join(missing)}"
    )


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--store-dir",default=STORE_DIR)
    ap.add_argument("--hide-docs",action="store_true")
    ap.add_argument("--no-rerank",action="store_true")
    ap.add_argument("--relax-context",action="store_true")
    args=ap.parse_args()

    global RERANK, RELAX_CONTEXT
    if args.no_rerank:
        RERANK=False
    if args.relax_context:
        RELAX_CONTEXT=True

    index,index_sum,index_title,metas,bm25,bm25_title=load_store(args.store_dir)
    indices={"full":index,"sum":index_sum,"title":index_title}

    while True:
        user_q=input("Query> ").strip()
        if not user_q:
            break
        raw_q=user_q
        user_q,meta_only=parse_meta_only(user_q)
        user_q,filters=parse_filters(user_q)
        allowed=filter_doc_ids(metas,filters)
        refined_q=""
        final_answer=""
        final_ctx=[]
        action=""
        last_queries=[]
        final_ids=[]
        for _ in range(MAX_ROUNDS):
            q=user_q
            if refined_q:
                q=f"{user_q}\nFocus: {refined_q}"
            mode=classify_query(user_q)
            queries=build_queries(user_q,mode,extra_hint=refined_q)
            last_queries=queries[:]
            if meta_only:
                weights={"title":1.0,"bm25":1.0}
                use_indices={"title":index_title}
                use_bm25=bm25_title
            else:
                weights=route_weights(mode)
                use_indices=indices
                use_bm25=bm25
            cand,rrf_scores,sim_scores=rrf_search_multi(use_indices,use_bm25,queries,TOP_K_RETRIEVE,weights,allowed=allowed)
            cand=lexical_prerank(user_q,metas,cand,use_bm25,PRE_RERANK_TOP_K)
            final_ids=rerank(user_q,metas,cand)
            ctx=[]
            retrieved=[]
            for i,idx in enumerate(final_ids):
                m=metas[idx]
                retrieved.append((i,idx,m,rrf_scores.get(idx,0.0),sim_scores.get(idx,0.0)))
                title=m.get("title","")
                link=m.get("link","")
                meta_line=format_meta(m)
                meta_line=f"\nMETA: {meta_line}" if meta_line else ""
                ctx.append(f"[{i+1}] {title}\nLINK: {link}{meta_line}\n{m['text'][:DOC_CHAR_LIMIT]}")
            show_docs = not args.hide_docs if SHOW_DOCS else False
            if show_docs:
                print("\n--- Retrieved docs ---")
                for rank,idx,m,rrf,sim in retrieved:
                    title=m.get("title","").strip() or "(no title)"
                    link=m.get("link","").strip()
                    text=m.get("text","")[:DOC_CHAR_LIMIT]
                    meta=(
                        f"doc_id={idx} row_id={m.get('row_id')} "
                        f"chunk_id={m.get('chunk_id')} rrf={rrf:.4f} sim={sim:.4f}"
                    )
                    meta_line=format_meta(m)
                    if meta_line:
                        meta+=f" meta=({meta_line})"
                    print(f"\n[{rank+1}] {title}\n{meta}")
                    if link:
                        print(f"link: {link}")
                    print(text)
                print("\n--- End docs ---\n")
            resp=answer_or_request(
                raw_q,
                ctx,
                allow_more=(_<MAX_ROUNDS-1),
                relax_context=RELAX_CONTEXT,
                mode=mode,
            )
            action=resp.get("action","")
            if action=="search_more":
                refined_q=resp.get("query","").strip()
                if not refined_q:
                    refined_q=refine_query(user_q,"more specific evidence")
                continue
            if action=="need_config":
                msg=resp.get("message","").strip() or "Configuration change needed."
                print(msg)
                log_event(args.store_dir,{"query":raw_q,"action":"need_config","message":msg})
                break
            if action!="answer":
                # fallback to standard answer step
                answer=resp.get("answer","") or NOT_FOUND_MSG
            else:
                answer=resp.get("answer","")
            evidence_block=build_evidence_block(resp)
            final_answer=answer + evidence_block if evidence_block and evidence_block not in answer else answer
            final_ctx=ctx
            if RELAX_CONTEXT:
                break
            supported,missing=verify_answer(raw_q,ctx,answer)
            if supported:
                break
            refined_q=refine_query(user_q,missing)
        if not final_ctx:
            print(NOT_FOUND_MSG)
            log_event(args.store_dir,{"query":raw_q,"action":"no_context","meta_only":meta_only})
        else:
            if NOT_FOUND_MSG in final_answer:
                print(NOT_FOUND_MSG)
            else:
                print(final_answer)
            log_event(args.store_dir,{
                "query":raw_q,
                "filters":filters,
                "meta_only":meta_only,
                "mode":mode,
                "queries":last_queries,
                "final_ids":final_ids,
                "action":action or "answer",
                "answer":final_answer,
                "ctx_count":len(final_ctx),
            })


if __name__=="__main__":
    main()
