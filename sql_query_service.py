"""
SQL Query Service
Handles secure SQL query generation, validation, and execution
"""
import os
import re
import asyncpg
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

load_dotenv()


class SqlQueryService:
    """Service for secure SQL query execution with validation"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.allowed_tables = os.getenv("SQL_ALLOWED_TABLES", "orders").split(",")
        self.max_results = int(os.getenv("SQL_MAX_RESULTS", "100"))

        # Blocked SQL keywords for security
        self.blocked_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
            "CREATE", "GRANT", "REVOKE", "EXECUTE", "EXEC",
            "INTO", "SET", "MERGE", "REPLACE"
        ]

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "chat_history"),
                min_size=5,
                max_size=20
            )
        return self.pool

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    def get_allowed_tables(self) -> List[str]:
        """Get list of whitelisted table names"""
        return [table.strip() for table in self.allowed_tables]

    async def get_table_schema(self, table_name: str) -> Optional[str]:
        """
        Get the schema (CREATE TABLE statement) for a specific table
        Only returns schema for whitelisted tables
        """
        if table_name not in self.get_allowed_tables():
            return None

        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Get column information
            columns = await conn.fetch("""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = $1
                ORDER BY ordinal_position
            """, table_name)

            if not columns:
                return None

            # Build CREATE TABLE statement
            schema = f"CREATE TABLE {table_name} (\n"
            column_defs = []
            for col in columns:
                col_def = f"  {col['column_name']} {col['data_type']}"
                if col['is_nullable'] == 'NO':
                    col_def += " NOT NULL"
                if col['column_default']:
                    col_def += f" DEFAULT {col['column_default']}"
                column_defs.append(col_def)

            schema += ",\n".join(column_defs)
            schema += "\n);"

            return schema

    async def get_all_schemas(self) -> Dict[str, str]:
        """Get schemas for all whitelisted tables"""
        schemas = {}
        for table in self.get_allowed_tables():
            schema = await self.get_table_schema(table)
            if schema:
                schemas[table] = schema
        return schemas

    def validate_sql(self, sql_query: str) -> tuple[bool, Optional[str]]:
        """
        Validate SQL query for security
        Returns (is_valid, error_message)
        """
        sql_upper = sql_query.upper()

        # Check for blocked keywords
        for keyword in self.blocked_keywords:
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                return False, f"Blocked keyword detected: {keyword}. Only SELECT queries are allowed."

        # Must start with SELECT (after whitespace)
        if not re.match(r'^\s*SELECT\s', sql_upper):
            return False, "Only SELECT queries are allowed"

        # Check if query references only whitelisted tables
        # Extract table names after FROM and JOIN keywords
        from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        join_pattern = r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'

        table_matches = re.findall(from_pattern, sql_upper) + re.findall(join_pattern, sql_upper)

        for table in table_matches:
            if table.lower() not in [t.lower() for t in self.get_allowed_tables()]:
                return False, f"Table '{table}' is not in the whitelist. Allowed tables: {', '.join(self.get_allowed_tables())}"

        # Check for semicolons (prevent query chaining)
        if sql_query.count(';') > 1:
            return False, "Multiple statements detected. Only single SELECT queries are allowed."

        return True, None

    async def execute_query(self, sql_query: str, user_id: str) -> tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Execute SQL query with user_id filtering
        Returns (success, results, error_message)
        """
        # Validate query first
        is_valid, error = self.validate_sql(sql_query)
        if not is_valid:
            return False, [], error

        try:
            pool = await self.get_pool()
            async with pool.acquire() as conn:
                # Inject user_id filter if not present
                # This ensures users only see their own data
                modified_query = self._inject_user_filter(sql_query, user_id)

                # Add LIMIT if not present
                if "LIMIT" not in modified_query.upper():
                    modified_query = f"{modified_query.rstrip(';')} LIMIT {self.max_results}"

                # Execute query
                rows = await conn.fetch(modified_query)

                # Convert to list of dicts
                results = [dict(row) for row in rows]

                return True, results, None

        except Exception as e:
            return False, [], f"Query execution error: {str(e)}"

    def _inject_user_filter(self, sql_query: str, user_id: str) -> str:
        """
        Inject user_id filter into WHERE clause
        If no WHERE clause exists, add one
        """
        sql_upper = sql_query.upper()

        # Check if user_id filter already exists
        if "USER_ID" in sql_upper:
            # Replace user_id placeholder with actual value
            # Handle both quoted and unquoted placeholders
            result = sql_query.replace("'$user_id'", f"'{user_id}'")  # Replace '$user_id' with 'value'
            result = result.replace("$user_id", f"'{user_id}'")  # Replace $user_id with 'value'
            result = result.replace("'$1'", f"'{user_id}'")  # Replace '$1' with 'value'
            result = result.replace("$1", f"'{user_id}'")  # Replace $1 with 'value'
            return result

        # Find WHERE clause
        where_match = re.search(r'\bWHERE\b', sql_upper)

        if where_match:
            # Insert user_id condition after WHERE
            insert_pos = where_match.end()
            modified = (
                sql_query[:insert_pos] +
                f" user_id = '{user_id}' AND" +
                sql_query[insert_pos:]
            )
        else:
            # Find position before ORDER BY, GROUP BY, HAVING, or LIMIT
            end_keywords = r'\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b'
            end_match = re.search(end_keywords, sql_upper)

            if end_match:
                insert_pos = end_match.start()
                modified = (
                    sql_query[:insert_pos] +
                    f" WHERE user_id = '{user_id}' " +
                    sql_query[insert_pos:]
                )
            else:
                # Add at the end (before semicolon if present)
                modified = sql_query.rstrip(';').strip() + f" WHERE user_id = '{user_id}'"

        return modified
