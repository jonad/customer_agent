"""
Document Agent Orchestrator
Coordinates the document search pipeline with multiple sub-agents
"""
from google.adk.agents import SequentialAgent
from .sub_agents import (
    QueryAnalyzerAgent,
    DocumentRetrieverAgent,
    RelevanceRankerAgent,
    AnswerSynthesizerAgent
)


class DocumentAgentOrchestrator:
    """
    Orchestrator for document search and retrieval pipeline

    Pipeline Flow:
    1. QueryAnalyzerAgent: Analyzes search query, extracts keywords and intent
    2. DocumentRetrieverAgent: Determines retrieval strategy (text search or embeddings)
    3. [External: Retrieve documents from database in main.py]
    4. RelevanceRankerAgent: Ranks and filters retrieved documents by relevance
    5. AnswerSynthesizerAgent: Generates natural language answer from top documents

    Note: Actual document retrieval happens in main.py using ChatHistoryService
    The RelevanceRankerAgent and AnswerSynthesizerAgent are called after retrieval
    """

    def __init__(self):
        # Query processing pipeline (runs before document retrieval)
        self.query_processing_agent = SequentialAgent(
            name="QueryProcessingPipeline",
            sub_agents=[
                QueryAnalyzerAgent,
                DocumentRetrieverAgent
            ],
            description="A pipeline that analyzes search queries and determines retrieval strategy"
        )

        # Result processing pipeline (runs after document retrieval)
        self.result_processing_agent = SequentialAgent(
            name="ResultProcessingPipeline",
            sub_agents=[
                RelevanceRankerAgent,
                AnswerSynthesizerAgent
            ],
            description="A pipeline that ranks documents and synthesizes answers"
        )
