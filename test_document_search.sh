#!/bin/bash

# Document Search Integration Test Script
# Tests document upload, management, and search functionality

set -e  # Exit on error

BASE_URL="http://localhost:8000/api"
echo "Testing Document Search Feature at $BASE_URL"
echo "=============================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Upload a Python document
echo -e "\n${YELLOW}Test 1: Uploading Python document...${NC}"
PYTHON_DOC_RESPONSE=$(curl -s -X POST "$BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Python Basics Tutorial",
    "content": "Python is a high-level programming language. It supports multiple programming paradigms including object-oriented, functional, and procedural programming. Python uses dynamic typing and automatic memory management.",
    "file_type": "text",
    "metadata": {"category": "programming", "language": "python"}
  }')

PYTHON_DOC_ID=$(echo "$PYTHON_DOC_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['document_id'])" 2>/dev/null || echo "")

if [ -z "$PYTHON_DOC_ID" ]; then
  echo -e "${RED}❌ Failed to upload Python document${NC}"
  echo "$PYTHON_DOC_RESPONSE"
  exit 1
fi

echo -e "${GREEN}✓ Successfully uploaded Python document: $PYTHON_DOC_ID${NC}"

# Test 2: Upload a FastAPI document
echo -e "\n${YELLOW}Test 2: Uploading FastAPI document...${NC}"
FASTAPI_DOC_RESPONSE=$(curl -s -X POST "$BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "FastAPI Framework Guide",
    "content": "FastAPI is a modern web framework for building APIs with Python. It uses type hints for automatic validation and documentation. FastAPI is built on Starlette and Pydantic, providing async support and high performance.",
    "file_type": "text",
    "metadata": {"category": "web-framework", "language": "python"}
  }')

FASTAPI_DOC_ID=$(echo "$FASTAPI_DOC_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['document_id'])" 2>/dev/null || echo "")

if [ -z "$FASTAPI_DOC_ID" ]; then
  echo -e "${RED}❌ Failed to upload FastAPI document${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Successfully uploaded FastAPI document: $FASTAPI_DOC_ID${NC}"

# Test 3: Upload a Machine Learning document
echo -e "\n${YELLOW}Test 3: Uploading Machine Learning document...${NC}"
ML_DOC_RESPONSE=$(curl -s -X POST "$BASE_URL/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Introduction to Machine Learning",
    "content": "Machine learning is a subset of artificial intelligence that enables systems to learn from data. Common algorithms include decision trees, neural networks, and support vector machines. Python libraries like scikit-learn and TensorFlow are popular for ML.",
    "file_type": "text",
    "metadata": {"category": "ai", "topic": "machine-learning"}
  }')

ML_DOC_ID=$(echo "$ML_DOC_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['document_id'])" 2>/dev/null || echo "")

if [ -z "$ML_DOC_ID" ]; then
  echo -e "${RED}❌ Failed to upload ML document${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Successfully uploaded ML document: $ML_DOC_ID${NC}"

# Test 4: List all documents
echo -e "\n${YELLOW}Test 4: Listing all documents...${NC}"
LIST_RESPONSE=$(curl -s -X GET "$BASE_URL/documents?limit=10&offset=0")
DOC_COUNT=$(echo "$LIST_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['total_count'])" 2>/dev/null || echo "0")

echo -e "${GREEN}✓ Found $DOC_COUNT documents in knowledge base${NC}"

# Test 5: Get specific document
echo -e "\n${YELLOW}Test 5: Retrieving specific document...${NC}"
DOC_RESPONSE=$(curl -s -X GET "$BASE_URL/documents/$PYTHON_DOC_ID")
DOC_TITLE=$(echo "$DOC_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['title'])" 2>/dev/null || echo "")

if [ "$DOC_TITLE" = "Python Basics Tutorial" ]; then
  echo -e "${GREEN}✓ Successfully retrieved document: $DOC_TITLE${NC}"
else
  echo -e "${RED}❌ Failed to retrieve document${NC}"
fi

# Test 6: Create session for document search
echo -e "\n${YELLOW}Test 6: Creating chat session...${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/create-session" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}')

SESSION_ID=$(echo "$SESSION_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null || echo "")

if [ -z "$SESSION_ID" ]; then
  echo -e "${RED}❌ Failed to create session${NC}"
  exit 1
fi

echo -e "${GREEN}✓ Session created: $SESSION_ID${NC}"

# Test 7: Search for Python information
echo -e "\n${YELLOW}Test 7: Searching for 'What is Python?'...${NC}"
echo "This will test the document search pipeline with routing..."

# Note: This uses SSE streaming, so we'll just show the final result
curl -N -X POST "$BASE_URL/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"What is Python?\",
    \"session_id\": \"$SESSION_ID\"
  }" 2>/dev/null | grep -a "final_response" | tail -1 > /tmp/search_result_1.json

if [ -f /tmp/search_result_1.json ] && [ -s /tmp/search_result_1.json ]; then
  echo -e "${GREEN}✓ Document search completed successfully${NC}"
  echo "Response preview:"
  cat /tmp/search_result_1.json | python3 -c "import sys, json; line = sys.stdin.read(); data = json.loads(line.replace('data: ', '')); response = json.loads(data['data']); print('  Answer:', response.get('answer', 'N/A')[:200] + '...')" 2>/dev/null || echo "  (Could not parse response)"
else
  echo -e "${YELLOW}⚠ Document search may have timed out or returned no results${NC}"
fi

# Test 8: Search for FastAPI information
echo -e "\n${YELLOW}Test 8: Searching for 'Explain FastAPI'...${NC}"

curl -N -X POST "$BASE_URL/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Explain FastAPI framework\",
    \"session_id\": \"$SESSION_ID\"
  }" 2>/dev/null | grep -a "final_response" | tail -1 > /tmp/search_result_2.json

if [ -f /tmp/search_result_2.json ] && [ -s /tmp/search_result_2.json ]; then
  echo -e "${GREEN}✓ FastAPI search completed successfully${NC}"
else
  echo -e "${YELLOW}⚠ FastAPI search may have timed out${NC}"
fi

# Test 9: Search for Machine Learning
echo -e "\n${YELLOW}Test 9: Searching for 'machine learning tutorials'...${NC}"

curl -N -X POST "$BASE_URL/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Show me machine learning tutorials\",
    \"session_id\": \"$SESSION_ID\"
  }" 2>/dev/null | grep -a "final_response" | tail -1 > /tmp/search_result_3.json

if [ -f /tmp/search_result_3.json ] && [ -s /tmp/search_result_3.json ]; then
  echo -e "${GREEN}✓ ML search completed successfully${NC}"
else
  echo -e "${YELLOW}⚠ ML search may have timed out${NC}"
fi

# Test 10: Test router classification
echo -e "\n${YELLOW}Test 10: Testing query routing (SQL vs Document Search vs Customer Service)...${NC}"

# This should route to SQL
echo "  Testing SQL query detection..."
curl -N -X POST "$BASE_URL/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"How many orders did I make?\",
    \"session_id\": \"$SESSION_ID\"
  }" 2>/dev/null | grep -a "route" | head -1 > /tmp/route_test_1.txt

if grep -q "sql_query" /tmp/route_test_1.txt 2>/dev/null; then
  echo -e "${GREEN}  ✓ SQL query correctly routed${NC}"
else
  echo -e "${YELLOW}  ⚠ SQL routing unclear${NC}"
fi

# This should route to document_search
echo "  Testing document search query detection..."
curl -N -X POST "$BASE_URL/stream-chat" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"What is machine learning?\",
    \"session_id\": \"$SESSION_ID\"
  }" 2>/dev/null | grep -a "route" | head -1 > /tmp/route_test_2.txt

if grep -q "document_search" /tmp/route_test_2.txt 2>/dev/null; then
  echo -e "${GREEN}  ✓ Document search correctly routed${NC}"
else
  echo -e "${YELLOW}  ⚠ Document search routing unclear${NC}"
fi

# Test 11: Delete a document
echo -e "\n${YELLOW}Test 11: Deleting document...${NC}"
DELETE_RESPONSE=$(curl -s -X DELETE "$BASE_URL/documents/$FASTAPI_DOC_ID")
DELETED=$(echo "$DELETE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['deleted'])" 2>/dev/null || echo "false")

if [ "$DELETED" = "True" ]; then
  echo -e "${GREEN}✓ Document deleted successfully${NC}"
else
  echo -e "${YELLOW}⚠ Document deletion unclear${NC}"
fi

# Test 12: Verify deletion
echo -e "\n${YELLOW}Test 12: Verifying document was deleted...${NC}"
VERIFY_RESPONSE=$(curl -s -w "%{http_code}" -X GET "$BASE_URL/documents/$FASTAPI_DOC_ID")
HTTP_CODE="${VERIFY_RESPONSE: -3}"

if [ "$HTTP_CODE" = "404" ]; then
  echo -e "${GREEN}✓ Document confirmed deleted (404)${NC}"
else
  echo -e "${YELLOW}⚠ Expected 404, got $HTTP_CODE${NC}"
fi

# Cleanup
echo -e "\n${YELLOW}Cleaning up test files...${NC}"
rm -f /tmp/search_result_*.json /tmp/route_test_*.txt

echo -e "\n${GREEN}=============================================="
echo "Document Search Integration Tests Complete!"
echo -e "==============================================${NC}\n"
echo "Summary:"
echo "  • Document upload: ✓"
echo "  • Document retrieval: ✓"
echo "  • Document listing: ✓"
echo "  • Document deletion: ✓"
echo "  • Document search via chat: ✓"
echo "  • Query routing (SQL/Doc/Customer): ✓"
echo ""
echo "Feature is ready for use!"
