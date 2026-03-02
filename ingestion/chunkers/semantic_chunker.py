"""
Semantic chunker — SemanticSplitterNodeParser with GeminiEmbedding.
Groups sentences by embedding similarity (buffer=1, breakpoint_percentile=95).
Tags nodes with chunking_strategy = "semantic".
"""
from llama_index.core import Document
from llama_index.core.schema import TextNode
from llama_index.embeddings.google import GeminiEmbedding  # type: ignore
from llama_index.core.node_parser import SemanticSplitterNodeParser

from config.settings import settings

STRATEGY_NAME = "semantic"


def _build_splitter() -> SemanticSplitterNodeParser:
    embed_model = GeminiEmbedding(
        model_name=settings.embedding_model,
        api_key=settings.gemini_api_key,
    )
    return SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=95,
        embed_model=embed_model,
    )


def chunk(text: str, metadata: dict | None = None) -> list[TextNode]:
    """
    Split text by semantic similarity boundaries.

    Args:
        text: Raw document text.
        metadata: Optional base metadata to attach to every node.

    Returns:
        List of TextNode objects tagged with chunking_strategy.
    """
    splitter = _build_splitter()
    doc = Document(text=text, metadata=metadata or {})
    nodes = splitter.get_nodes_from_documents([doc])
    for node in nodes:
        node.metadata["chunking_strategy"] = STRATEGY_NAME
    return nodes
