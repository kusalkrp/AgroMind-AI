"""
Parent-child chunker — HierarchicalNodeParser([2048, 512, 128]).
Creates parent (2048), child (512), and leaf (128) nodes.
Tags ALL nodes with chunking_strategy = "parent_child".
"""
from llama_index.core import Document
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.core.schema import TextNode

STRATEGY_NAME = "parent_child"
CHUNK_SIZES = [2048, 512, 128]


def chunk(text: str, metadata: dict | None = None) -> list[TextNode]:
    """
    Split text into a three-level hierarchy (parent → child → leaf).

    Returns all nodes (all levels) tagged with chunking_strategy.
    For retrieval purposes, leaf nodes (128 tokens) are typically indexed.

    Args:
        text: Raw document text.
        metadata: Optional base metadata to attach to every node.

    Returns:
        List of all TextNode objects (all hierarchy levels) tagged with chunking_strategy.
    """
    splitter = HierarchicalNodeParser.from_defaults(chunk_sizes=CHUNK_SIZES)
    doc = Document(text=text, metadata=metadata or {})
    all_nodes = splitter.get_nodes_from_documents([doc])
    for node in all_nodes:
        node.metadata["chunking_strategy"] = STRATEGY_NAME
    return all_nodes


def get_leaf_chunks(text: str, metadata: dict | None = None) -> list[TextNode]:
    """
    Return only leaf (smallest) nodes — 128 token chunks for embedding.

    Args:
        text: Raw document text.
        metadata: Optional base metadata.

    Returns:
        List of leaf TextNode objects.
    """
    all_nodes = chunk(text, metadata)
    return get_leaf_nodes(all_nodes)
