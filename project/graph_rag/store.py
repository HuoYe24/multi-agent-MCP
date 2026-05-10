import itertools
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Iterable

import config


DOMAIN_TERMS = {
    "七天无理由": ["七天无理由", "7天无理由", "seven-day return"],
    "退货政策": ["退货", "退货政策", "return policy", "return"],
    "退款政策": ["退款", "退款政策", "refund policy", "refund"],
    "换货政策": ["换货", "换新", "exchange"],
    "售后服务": ["售后", "售后服务", "after-sales", "after sales"],
    "保修政策": ["保修", "质保", "warranty"],
    "物流配送": ["物流", "配送", "快递", "发货", "shipment", "shipping", "delivery"],
    "订单": ["订单", "order"],
    "商品": ["商品", "产品", "product", "item"],
    "优惠券": ["优惠券", "coupon"],
    "促销活动": ["促销", "活动", "满减", "折扣", "campaign", "promotion"],
    "发票": ["发票", "invoice"],
    "支付": ["支付", "付款", "payment"],
    "运费": ["运费", "邮费", "shipping fee"],
    "运费险": ["运费险"],
    "人工客服": ["人工客服", "客服", "manual service", "human support"],
}


class GraphRAGStore:
    """Lightweight JSON-backed graph for e-commerce knowledge-base relations."""

    def __init__(self, store_path: str = None):
        self.store_path = Path(store_path or config.GRAPH_STORE_PATH)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.store_path / "graph.json"

    @staticmethod
    def _empty_graph() -> dict:
        return {"nodes": {}, "edges": {}, "chunks": {}}

    @staticmethod
    def _edge_key(a: str, b: str) -> str:
        left, right = sorted([a, b])
        return f"{left}||{right}"

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _load(self) -> dict:
        if not self.graph_file.exists():
            return self._empty_graph()
        try:
            data = json.loads(self.graph_file.read_text(encoding="utf-8"))
        except Exception:
            return self._empty_graph()
        data.setdefault("nodes", {})
        data.setdefault("edges", {})
        data.setdefault("chunks", {})
        return data

    def _save(self, graph: dict) -> None:
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.graph_file.write_text(
            json.dumps(graph, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _add_limited(items: list[str], value: str, limit: int = 20) -> list[str]:
        if value and value not in items:
            items.append(value)
        return items[-limit:]

    @staticmethod
    def _query_terms(text: str) -> set[str]:
        lowered = str(text or "").lower()
        latin = re.findall(r"[a-z0-9][a-z0-9_-]{1,}", lowered)
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
        return {term for term in latin + chinese if len(term) >= 2}

    def extract_entities(self, text: str) -> list[str]:
        normalized = self._normalize(text)
        lowered = normalized.lower()
        entities: list[str] = []

        for canonical, aliases in DOMAIN_TERMS.items():
            if any(alias.lower() in lowered for alias in aliases):
                entities.append(canonical)

        header_entities = re.findall(r"^#{1,4}\s+(.+)$", normalized, flags=re.MULTILINE)
        quoted_entities = re.findall(r"[「《\"]([^」》\"]{2,30})[」》\"]", normalized)
        product_like = re.findall(
            r"[\u4e00-\u9fffA-Za-z0-9_-]{2,24}(?:耳机|手机壳|充电器|电脑|相机|面膜|服饰|鞋|包|家电|会员|套餐)",
            normalized,
        )
        english_names = re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}(?:\s+[A-Z][A-Za-z0-9_-]{2,}){0,3}\b", normalized)

        for raw in header_entities + quoted_entities + product_like + english_names:
            entity = self._normalize(raw).strip("#:：- ")
            if 2 <= len(entity) <= 40:
                entities.append(entity)

        deduped = []
        seen = set()
        for entity in entities:
            key = entity.lower()
            if key not in seen:
                deduped.append(entity)
                seen.add(key)
        return deduped[:20]

    def index_parent_chunks(self, document_stem: str, source_name: str, parent_chunks: Iterable) -> None:
        if not config.GRAPH_RAG_ENABLED:
            return

        graph = self._load()
        self.delete_document(document_stem, save=False, graph=graph)

        for parent_id, doc in parent_chunks:
            content = self._normalize(getattr(doc, "page_content", ""))
            entities = self.extract_entities(content)
            if not entities:
                continue

            graph["chunks"][parent_id] = {
                "parent_id": parent_id,
                "document_stem": document_stem,
                "source": source_name,
                "content": content[:1200],
                "entities": entities,
            }

            for entity in entities:
                node = graph["nodes"].setdefault(
                    entity,
                    {"label": entity, "mentions": 0, "sources": [], "parent_ids": []},
                )
                node["mentions"] = int(node.get("mentions", 0)) + 1
                node["sources"] = self._add_limited(node.setdefault("sources", []), source_name)
                node["parent_ids"] = self._add_limited(node.setdefault("parent_ids", []), parent_id, limit=50)

            for left, right in itertools.combinations(entities[:12], 2):
                key = self._edge_key(left, right)
                edge = graph["edges"].setdefault(
                    key,
                    {"source": sorted([left, right])[0], "target": sorted([left, right])[1], "weight": 0, "sources": [], "parent_ids": []},
                )
                edge["weight"] = int(edge.get("weight", 0)) + 1
                edge["sources"] = self._add_limited(edge.setdefault("sources", []), source_name)
                edge["parent_ids"] = self._add_limited(edge.setdefault("parent_ids", []), parent_id, limit=50)

        self._save(graph)

    def delete_document(self, document_stem: str, *, save: bool = True, graph: dict = None) -> int:
        graph = graph or self._load()
        removed_parent_ids = [
            parent_id
            for parent_id, chunk in graph.get("chunks", {}).items()
            if chunk.get("document_stem") == document_stem
        ]
        if not removed_parent_ids:
            if save:
                self._save(graph)
            return 0

        for parent_id in removed_parent_ids:
            graph["chunks"].pop(parent_id, None)

        removed_set = set(removed_parent_ids)
        for entity in list(graph.get("nodes", {}).keys()):
            node = graph["nodes"][entity]
            node["parent_ids"] = [pid for pid in node.get("parent_ids", []) if pid not in removed_set]
            if not node["parent_ids"]:
                graph["nodes"].pop(entity, None)

        for edge_key in list(graph.get("edges", {}).keys()):
            edge = graph["edges"][edge_key]
            edge["parent_ids"] = [pid for pid in edge.get("parent_ids", []) if pid not in removed_set]
            if not edge["parent_ids"]:
                graph["edges"].pop(edge_key, None)

        if save:
            self._save(graph)
        return len(removed_parent_ids)

    def clear(self) -> None:
        self.store_path.mkdir(parents=True, exist_ok=True)
        for child in self.store_path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

    def search(self, query: str, max_results: int = None) -> dict:
        graph = self._load()
        if not graph.get("chunks"):
            return {"entities": [], "relations": [], "chunks": []}

        max_results = max_results or config.GRAPH_RAG_MAX_RESULTS
        query_entities = self.extract_entities(query)
        query_entity_set = {entity.lower() for entity in query_entities}
        query_terms = self._query_terms(query)

        scored_chunks = []
        for chunk in graph["chunks"].values():
            chunk_entities = {entity.lower() for entity in chunk.get("entities", [])}
            entity_score = len(query_entity_set & chunk_entities) * 4
            content_terms = self._query_terms(chunk.get("content", ""))
            term_score = len(query_terms & content_terms)
            score = entity_score + term_score
            if score > 0:
                scored_chunks.append((score, chunk))

        if not scored_chunks and query_terms:
            for chunk in graph["chunks"].values():
                content = chunk.get("content", "").lower()
                score = sum(1 for term in query_terms if term.lower() in content)
                if score > 0:
                    scored_chunks.append((score, chunk))

        scored_chunks.sort(key=lambda item: item[0], reverse=True)
        selected_chunks = [chunk for _, chunk in scored_chunks[:max_results]]

        parent_ids = {chunk["parent_id"] for chunk in selected_chunks}
        entity_counter = Counter()
        for chunk in selected_chunks:
            entity_counter.update(chunk.get("entities", []))
        selected_entities = [entity for entity, _ in entity_counter.most_common(12)]

        relations = []
        for edge in graph.get("edges", {}).values():
            if parent_ids and not (set(edge.get("parent_ids", [])) & parent_ids):
                continue
            if edge.get("source") in selected_entities or edge.get("target") in selected_entities:
                relations.append(edge)
        relations.sort(key=lambda edge: int(edge.get("weight", 0)), reverse=True)

        return {
            "entities": selected_entities,
            "relations": relations[:max_results],
            "chunks": selected_chunks,
        }

    def format_search_results(self, query: str, max_results: int = None) -> str:
        result = self.search(query, max_results=max_results)
        if not result["chunks"]:
            return "NO_RELEVANT_GRAPH_CONTEXT"

        lines = ["[GraphRAG Context]"]
        if result["entities"]:
            lines.append("Entities: " + ", ".join(result["entities"]))

        if result["relations"]:
            lines.append("Relations:")
            for edge in result["relations"][:8]:
                lines.append(
                    f"- {edge.get('source')} <-> {edge.get('target')} "
                    f"(weight={edge.get('weight')}, sources={', '.join(edge.get('sources', []))})"
                )

        lines.append("Evidence:")
        for idx, chunk in enumerate(result["chunks"][: max_results or config.GRAPH_RAG_MAX_RESULTS], 1):
            lines.append(
                f"[Graph Evidence {idx}]\n"
                f"Parent ID: {chunk.get('parent_id')}\n"
                f"File Name: {chunk.get('source')}\n"
                f"Entities: {', '.join(chunk.get('entities', []))}\n"
                f"Content: {chunk.get('content', '').strip()}"
            )

        return "\n\n".join(lines)
