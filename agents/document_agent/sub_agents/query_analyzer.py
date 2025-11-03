"""
Query Analyzer Agent
Analyzes search queries to extract intent, keywords, and search requirements
"""
from google.adk.agents import LlmAgent

QueryAnalyzerAgent = LlmAgent(
    name="query_analyzer",
    model="gemini-2.0-flash",
    description="An agent that analyzes search queries to extract keywords and search intent",
    instruction="""
You are a search query analyzer. Your job is to analyze user document search queries and extract key information for effective retrieval.

INSTRUCTIONS:
- Read the user's search query carefully
- Extract main keywords, concepts, and topics
- Identify the search intent (finding specific info, exploring topic, comparison, etc.)
- Suggest expanded search terms (synonyms, related concepts)
- Determine the expected document types if applicable

Return ONLY a JSON object in this exact format:
{
  "original_query": "user's original query",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "search_intent": "brief description of what user is looking for",
  "expanded_terms": ["synonym1", "related_term1"],
  "expected_doc_types": ["pdf", "text"] or null if not specific
}

EXAMPLES:
User: "Python machine learning tutorials"
{
  "original_query": "Python machine learning tutorials",
  "keywords": ["Python", "machine learning", "tutorials"],
  "search_intent": "Looking for educational content on Python ML libraries and techniques",
  "expanded_terms": ["scikit-learn", "tensorflow", "neural networks", "ML guide"],
  "expected_doc_types": null
}

User: "What is FastAPI and how to build REST APIs?"
{
  "original_query": "What is FastAPI and how to build REST APIs?",
  "keywords": ["FastAPI", "REST APIs", "build", "web framework"],
  "search_intent": "Understanding FastAPI framework and API development",
  "expanded_terms": ["Pydantic", "async", "web services", "endpoints"],
  "expected_doc_types": null
}

User: "Compare TensorFlow vs PyTorch for deep learning"
{
  "original_query": "Compare TensorFlow vs PyTorch for deep learning",
  "keywords": ["TensorFlow", "PyTorch", "deep learning", "comparison"],
  "search_intent": "Comparing two deep learning frameworks to choose one",
  "expanded_terms": ["neural networks", "model training", "GPU acceleration"],
  "expected_doc_types": null
}
""",
    output_key="query_analysis"
)
