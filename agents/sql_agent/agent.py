"""
SQL Agent Orchestrator
Coordinates the text-to-SQL pipeline with multiple sub-agents
"""
from google.adk.agents import SequentialAgent
from .sub_agents import (
    SchemaRetrieverAgent,
    SqlGeneratorAgent,
    SqlValidatorAgent,
    ResultFormatterAgent
)


class SqlAgentOrchestrator:
    """
    Orchestrator for SQL query generation and execution pipeline

    Pipeline Flow:
    1. SchemaRetrieverAgent: Identifies which tables are needed
    2. SqlGeneratorAgent: Generates SQL query from natural language
    3. SqlValidatorAgent: Validates SQL for security and correctness
    4. [External: Execute query in main.py]
    5. ResultFormatterAgent: Formats results into natural language

    Note: Actual query execution happens in main.py using SqlQueryService
    The ResultFormatterAgent is called separately after execution
    """

    def __init__(self):
        # SQL generation pipeline (runs before execution)
        # NOTE: Using only SqlGeneratorAgent because SequentialAgent stops after first LlmAgent's final_response
        # SqlValidator logic is built into SqlGenerator's instructions instead
        self.sql_generation_agent = SqlGeneratorAgent

        # Result formatting (runs after execution)
        self.result_formatter = ResultFormatterAgent
