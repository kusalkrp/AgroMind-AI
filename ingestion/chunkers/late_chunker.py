"""
Late chunker — SentenceSplitter(512, overlap=100) with document-level metadata propagation.
Unlike other chunkers, the document's full text is embedded at the doc level first,
then chunks inherit doc-level metadata for "late interaction" retrieval (ColBERT-style).
Tags nodes with chunking_strategy = "late".
"""
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode

STRATEGY_NAME = "late"


def chunk(text: str, metadata: dict | None = None) -> list[TextNode]:
    """
    Split text with doc-level metadata propagation to each chunk.

    Every child node inherits a "doc_summary" field in metadata — the first
    512 characters of the document — enabling late-interaction scoring at
    retrieval time against the full document representation.

    Args:
        text: Raw document text.
        metadata: Optional base metadata to attach to every node.

    Returns:
        List of TextNode objects tagged with chunking_strategy and doc_summary.
    """
    base_metadata = dict(metadata or {})
    # Attach condensed doc-level context to every chunk
    base_metadata["doc_summary"] = text[:512].replace("\n", " ").strip()

    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=100)
    doc = Document(text=text, metadata=base_metadata)
    nodes = splitter.get_nodes_from_documents([doc])
    for node in nodes:
        node.metadata["chunking_strategy"] = STRATEGY_NAME
    return nodes
