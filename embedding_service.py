"""
Embedding Service for Document Search
Provides text embeddings for semantic search using Vertex AI
"""
import os
from typing import List, Optional
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
import asyncio


class EmbeddingService:
    """
    Service for generating text embeddings using Vertex AI
    Supports semantic search with advanced text understanding
    """

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model_name = "text-embedding-004"  # Latest Vertex AI embedding model
        self.embedding_dimension = 768
        self.use_embeddings = os.getenv("USE_EMBEDDINGS", "true").lower() == "true"

        # Initialize Vertex AI client
        if self.use_embeddings:
            try:
                aiplatform.init(project=self.project_id, location=self.location)
                self._model = None  # Lazy load on first use
                print(f"✅ Vertex AI initialized for embeddings (project: {self.project_id})")
            except Exception as e:
                print(f"⚠️  Failed to initialize Vertex AI: {e}")
                print("   Falling back to text-based search")
                self.use_embeddings = False

    def _get_model(self):
        """Lazy load the embedding model"""
        if self._model is None:
            self._model = TextEmbeddingModel.from_pretrained(self.model_name)
        return self._model

    async def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> Optional[List[float]]:
        """
        Generate embedding vector for a text string using Vertex AI

        Args:
            text: Input text to embed (max 20,000 characters)
            task_type: Type of embedding task - "RETRIEVAL_DOCUMENT" for documents,
                      "RETRIEVAL_QUERY" for search queries

        Returns:
            List of floats representing the embedding vector (768 dimensions)
            Returns None if embeddings are disabled or generation fails
        """
        if not self.use_embeddings:
            return None

        # Truncate text if too long (Vertex AI limit is 20,000 chars)
        if len(text) > 20000:
            text = text[:20000]

        try:
            # Run the synchronous API call in a thread pool to avoid blocking
            model = await asyncio.to_thread(self._get_model)

            # Create embedding input with task type for better results
            embedding_input = TextEmbeddingInput(text=text, task_type=task_type)

            # Generate embedding
            embeddings = await asyncio.to_thread(model.get_embeddings, [embedding_input])

            if embeddings and len(embeddings) > 0:
                return embeddings[0].values

            return None

        except Exception as e:
            print(f"⚠️  Error generating embedding: {e}")
            print(f"   Text length: {len(text)} chars")
            return None

    async def generate_embeddings_batch(
        self,
        texts: List[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 5
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts in batch using Vertex AI

        Args:
            texts: List of input texts (each max 20,000 chars)
            task_type: Type of embedding task
            batch_size: Number of texts to process in each API call (max 250, but 5 recommended for stability)

        Returns:
            List of embedding vectors, one per input text
        """
        if not self.use_embeddings or not texts:
            return [None] * len(texts)

        results = [None] * len(texts)

        try:
            model = await asyncio.to_thread(self._get_model)

            # Process in batches to avoid API limits
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]

                # Truncate each text if needed
                truncated_batch = [text[:20000] if len(text) > 20000 else text for text in batch]

                # Create embedding inputs
                embedding_inputs = [
                    TextEmbeddingInput(text=text, task_type=task_type)
                    for text in truncated_batch
                ]

                # Generate embeddings for batch
                embeddings = await asyncio.to_thread(model.get_embeddings, embedding_inputs)

                # Store results
                for j, embedding in enumerate(embeddings):
                    if embedding and embedding.values:
                        results[i + j] = embedding.values

        except Exception as e:
            print(f"⚠️  Error generating batch embeddings: {e}")
            print(f"   Batch size: {len(texts)} texts")

        return results

    def calculate_cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        if not embedding1 or not embedding2:
            return 0.0

        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))

        # Calculate magnitudes
        magnitude1 = sum(a * a for a in embedding1) ** 0.5
        magnitude2 = sum(b * b for b in embedding2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Cosine similarity
        return dot_product / (magnitude1 * magnitude2)

    async def find_similar_documents(
        self,
        query_embedding: List[float],
        document_embeddings: List[dict],
        top_k: int = 10,
        threshold: float = 0.5
    ) -> List[dict]:
        """
        Find most similar documents based on embedding similarity

        Args:
            query_embedding: Query embedding vector
            document_embeddings: List of dicts with 'document_id' and 'embedding'
            top_k: Number of top results to return
            threshold: Minimum similarity score

        Returns:
            List of documents with similarity scores, sorted by relevance
        """
        if not query_embedding:
            return []

        results = []
        for doc in document_embeddings:
            if doc.get('embedding'):
                similarity = self.calculate_cosine_similarity(
                    query_embedding,
                    doc['embedding']
                )
                if similarity >= threshold:
                    results.append({
                        **doc,
                        'relevance_score': similarity
                    })

        # Sort by relevance score descending
        results.sort(key=lambda x: x['relevance_score'], reverse=True)

        return results[:top_k]


# Global embedding service instance
embedding_service = EmbeddingService()
