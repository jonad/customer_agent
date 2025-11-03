"""
Router Agent Orchestrator
Classifies user queries to route them to the appropriate pipeline
"""
from .llm_agent import RouterLlmAgent


class RouterOrchestrator:
    """
    Orchestrator for query routing classification

    Uses a single LLM agent to classify queries into three types:
    - sql_query: Questions about data, orders, statistics
    - document_search: Questions seeking information from documents, tutorials, documentation
    - customer_service: Support, billing, general inquiries
    """

    def __init__(self):
        # Use LlmAgent directly (no SequentialAgent wrapper needed for single agent)
        self.root_agent = RouterLlmAgent
