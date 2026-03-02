"""
Unit tests for agents/intent_agent.py

Mocks: call_gemini, hybrid_search, rerank_texts, grade_chunks,
       filter_relevant_chunks, get_overall_grade
"""
from unittest.mock import MagicMock, patch

import pytest

from orchestration.state import initial_state


def _make_state(**kwargs):
    state = initial_state(query="test query", district="Kandy", crop="paddy")
    state.update(kwargs)
    return state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _graded_chunk(text: str, score: float = 0.8, relevance: str = "relevant"):
    g = MagicMock()
    g.chunk = text
    g.score = score
    rel = MagicMock()
    rel.value = relevance
    g.relevance = rel
    return g


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestIntentNode:

    def test_intent_classifies_planning(self):
        """LLM JSON with intent=planning sets state['intent']=='planning'."""
        state = _make_state()
        graded = [_graded_chunk("chunk1")]

        with patch("agents.intent_agent.call_gemini",
                   return_value='{"intent":"planning","crop":"paddy","district":"Kandy","sub_tasks":[]}'), \
             patch("agents.intent_agent.hybrid_search", return_value=["chunk1"]), \
             patch("agents.intent_agent.rerank_texts", return_value=["chunk1"]), \
             patch("agents.intent_agent.grade_chunks", return_value=graded), \
             patch("agents.intent_agent.filter_relevant_chunks",
                   return_value=(["chunk1"], False)), \
             patch("agents.intent_agent.get_overall_grade", return_value="CORRECT"):
            from agents.intent_agent import intent_node
            result = intent_node(state)

        assert result["intent"] == "planning"

    def test_intent_sets_semantic_context(self):
        """filter_relevant_chunks returning 2 chunks sets len(semantic_context)==2."""
        state = _make_state()
        graded = [_graded_chunk("chunk1"), _graded_chunk("chunk2")]

        with patch("agents.intent_agent.call_gemini",
                   return_value='{"intent":"disease","crop":"paddy","district":"Kandy","sub_tasks":[]}'), \
             patch("agents.intent_agent.hybrid_search", return_value=["chunk1", "chunk2"]), \
             patch("agents.intent_agent.rerank_texts", return_value=["chunk1", "chunk2"]), \
             patch("agents.intent_agent.grade_chunks", return_value=graded), \
             patch("agents.intent_agent.filter_relevant_chunks",
                   return_value=(["chunk1", "chunk2"], False)), \
             patch("agents.intent_agent.get_overall_grade", return_value="CORRECT"):
            from agents.intent_agent import intent_node
            result = intent_node(state)

        assert len(result["semantic_context"]) == 2

    def test_intent_crag_grade_correct(self):
        """get_overall_grade returning 'CORRECT' sets state['crag_grade']=='CORRECT'."""
        state = _make_state()
        graded = [_graded_chunk("chunk1")]

        with patch("agents.intent_agent.call_gemini",
                   return_value='{"intent":"general","crop":null,"district":null,"sub_tasks":[]}'), \
             patch("agents.intent_agent.hybrid_search", return_value=["chunk1"]), \
             patch("agents.intent_agent.rerank_texts", return_value=["chunk1"]), \
             patch("agents.intent_agent.grade_chunks", return_value=graded), \
             patch("agents.intent_agent.filter_relevant_chunks",
                   return_value=(["chunk1"], False)), \
             patch("agents.intent_agent.get_overall_grade", return_value="CORRECT"):
            from agents.intent_agent import intent_node
            result = intent_node(state)

        assert result["crag_grade"] == "CORRECT"

    def test_intent_llm_failure_defaults_general(self):
        """When call_gemini raises, intent falls back to 'general'."""
        state = _make_state()
        graded = [_graded_chunk("chunk1")]

        with patch("agents.intent_agent.call_gemini",
                   side_effect=Exception("API quota exceeded")), \
             patch("agents.intent_agent.hybrid_search", return_value=["chunk1"]), \
             patch("agents.intent_agent.rerank_texts", return_value=["chunk1"]), \
             patch("agents.intent_agent.grade_chunks", return_value=graded), \
             patch("agents.intent_agent.filter_relevant_chunks",
                   return_value=(["chunk1"], False)), \
             patch("agents.intent_agent.get_overall_grade", return_value="INCORRECT"):
            from agents.intent_agent import intent_node
            result = intent_node(state)

        assert result["intent"] == "general"

    def test_intent_appends_reasoning_trace(self):
        """reasoning_trace should grow by at least 1 entry after intent_node runs."""
        state = _make_state(reasoning_trace=["seed"])
        graded = [_graded_chunk("chunk1")]
        initial_len = len(state["reasoning_trace"])

        with patch("agents.intent_agent.call_gemini",
                   return_value='{"intent":"market","crop":"paddy","district":"Kandy","sub_tasks":[]}'), \
             patch("agents.intent_agent.hybrid_search", return_value=["chunk1"]), \
             patch("agents.intent_agent.rerank_texts", return_value=["chunk1"]), \
             patch("agents.intent_agent.grade_chunks", return_value=graded), \
             patch("agents.intent_agent.filter_relevant_chunks",
                   return_value=(["chunk1"], False)), \
             patch("agents.intent_agent.get_overall_grade", return_value="AMBIGUOUS"):
            from agents.intent_agent import intent_node
            result = intent_node(state)

        assert len(result["reasoning_trace"]) > initial_len
