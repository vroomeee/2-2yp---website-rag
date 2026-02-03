"""
FastAPI server with SSE streaming endpoint for the RAG chatbot.

Usage:
    python api_server.py
"""

import asyncio
import json
import os
import sys
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="RAG Chat API")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
VER_DIR = os.path.join(PROJECT_ROOT, "ver1.0")
sys.path.insert(0, VER_DIR)

from rag_query import (  # noqa: E402
    NOT_FOUND_MSG,
    MAX_ROUNDS,
    TOP_K_RETRIEVE,
    TOP_K_FINAL,
    DOC_CHAR_LIMIT,
    load_store,
    classify_query,
    build_queries,
    route_weights,
    rrf_search_multi,
    rerank,
    answer_or_request,
    verify_answer,
    refine_query,
    parse_filters,
    parse_meta_only,
    filter_doc_ids,
    lexical_prerank,
    PRE_RERANK_TOP_K,
    format_meta,
    build_evidence_block,
)

STORE_DIR = os.path.join(VER_DIR, "rag_store")
index_full, index_summary, index_title, metas, bm25, bm25_title = load_store(STORE_DIR)
indices = {"full": index_full, "sum": index_summary, "title": index_title}

MAX_CTX_DOCS = 24


class ChatRequest(BaseModel):
    query: str
    conversation_id: str = ""
    relax_context: bool = False


def _build_docs_payload(doc_ids, doc_index, score_map, sim_map):
    docs = []
    for doc_id in doc_ids:
        idx = doc_index[doc_id]
        m = metas[doc_id]
        rrf = score_map.get(doc_id)
        sim = sim_map.get(doc_id)
        docs.append(
            {
                "index": idx,
                "title": m.get("title", ""),
                "link": m.get("link", ""),
                "text": m.get("text", "")[:DOC_CHAR_LIMIT],
                "meta": format_meta(m),
                "rrf_score": float(rrf) if rrf is not None else None,
                "sim_score": float(sim) if sim is not None else None,
            }
        )
    return docs


def _build_context(doc_ids, doc_index):
    ctx = []
    for doc_id in doc_ids:
        idx = doc_index[doc_id]
        m = metas[doc_id]
        title = m.get("title", "")
        link = m.get("link", "")
        meta_line = format_meta(m)
        meta_line = f"\nMETA: {meta_line}" if meta_line else ""
        ctx.append(
            f"[{idx}] {title}\nLINK: {link}{meta_line}\n{m.get('text','')[:DOC_CHAR_LIMIT]}"
        )
    return ctx


async def rag_stream(query: str, relax_context: bool = False):
    clean_query, meta_only = parse_meta_only(query)
    clean_query, filters = parse_filters(clean_query)
    allowed = filter_doc_ids(metas, filters)

    refined_q = ""
    doc_list = []
    doc_index = {}
    score_map = {}
    sim_map = {}
    final_answer = ""
    action = ""
    mode = "other"

    for round_idx in range(MAX_ROUNDS):
        mode = classify_query(clean_query)
        queries = build_queries(clean_query, mode, extra_hint=refined_q)
        if meta_only:
            weights = {"title": 1.0, "bm25": 1.0}
            use_indices = {"title": index_title}
            use_bm25 = bm25_title
        else:
            weights = route_weights(mode)
            use_indices = indices
            use_bm25 = bm25

        cand, rrf_scores, sim_scores = rrf_search_multi(
            use_indices, use_bm25, queries, TOP_K_RETRIEVE, weights, allowed=allowed
        )
        cand = lexical_prerank(clean_query, metas, cand, use_bm25, PRE_RERANK_TOP_K)
        final_ids = rerank(clean_query, metas, cand)

        for doc_id in final_ids:
            if doc_id in doc_index:
                score_map[doc_id] = rrf_scores.get(doc_id, score_map.get(doc_id))
                sim_map[doc_id] = sim_scores.get(doc_id, sim_map.get(doc_id))
                continue
            if len(doc_list) >= MAX_CTX_DOCS:
                continue
            doc_list.append(doc_id)
            doc_index[doc_id] = len(doc_list)
            score_map[doc_id] = rrf_scores.get(doc_id)
            sim_map[doc_id] = sim_scores.get(doc_id)

        ctx = _build_context(doc_list, doc_index)
        docs_payload = _build_docs_payload(doc_list, doc_index, score_map, sim_map)
        yield f"data: {json.dumps({'type': 'docs', 'documents': docs_payload}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0)

        resp = answer_or_request(
            query,
            ctx,
            allow_more=(round_idx < MAX_ROUNDS - 1),
            relax_context=relax_context,
            mode=mode,
        )
        action = resp.get("action", "")
        if action == "search_more":
            refined_q = resp.get("query", "").strip() or refine_query(
                clean_query, "more specific evidence"
            )
            continue
        if action == "need_config":
            final_answer = resp.get("message", "").strip() or "Configuration change needed."
            break
        if action != "answer":
            final_answer = resp.get("answer", "") or NOT_FOUND_MSG
        else:
            final_answer = resp.get("answer", "")

        evidence_block = build_evidence_block(resp)
        if evidence_block and evidence_block not in final_answer:
            final_answer += evidence_block

        if relax_context:
            break
        supported, missing = verify_answer(query, ctx, final_answer)
        if supported:
            break
        refined_q = refine_query(clean_query, missing)

    if not doc_list and not final_answer:
        final_answer = NOT_FOUND_MSG

    full_text = ""
    chunk_size = 3
    for i in range(0, len(final_answer), chunk_size):
        chunk = final_answer[i : i + chunk_size]
        full_text += chunk
        yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.02)

    yield f"data: {json.dumps({'type': 'done', 'full_answer': full_text}, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    return StreamingResponse(
        rag_stream(req.query, relax_context=req.relax_context),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
