"""
Fixed-size chunker — SentenceSplitter(chunk_size=512, chunk_overlap=50).
Tags each node with chunking_strategy = "fixed".
"""
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode

STRATEGY_NAME = "fixed"


def chunk(text: str, metadata: dict | None = None) -> list[TextNode]:
    """
    Split text into fixed-size chunks with minimal overlap.

    Args:
        text: Raw document text.
        metadata: Optional base metadata to attach to every node.

    Returns:
        List of TextNode objects tagged with chunking_strategy.
    """
    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    doc = Document(text=text, metadata=metadata or {})
    nodes = splitter.get_nodes_from_documents([doc])
    for node in nodes:
        node.metadata["chunking_strategy"] = STRATEGY_NAME
    return nodes
