import psycopg2
import json
import os
from dotenv import load_dotenv

from typing import List, Any, Optional
from psycopg2.extras import RealDictCursor

from miniorm.exceptions_base import (
    ConnectionError,
    SqlSyntaxError,
    QueryExecutionError,
    ConfigurationError
)

# Dynamically resolve path to properties.json inside the miniorm package
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "properties.json")

class Pgsql:
    """
    Provides PostgreSQL connection and query utilities.
    Loads configuration from a JSON file and allows basic operations like connect, execute, fetch columns, and disconnect.
    """
    def __init__(self):
        """
        Initializes the Pgsql instance by loading DB settings from environment variables (.env).
        """
        self.connection = None

        # Load environment variables
        load_dotenv()

        try:
            self.database_params = {
                "user": os.getenv("DB_USER"),
                "password": os.getenv("DB_PASSWORD"),
                "host": os.getenv("DB_HOST"),
                "port": int(os.getenv("DB_PORT")),
                "database": os.getenv("DB_NAME")
            }

            # Validar se alguma variável essencial está faltando
            for key, value in self.database_params.items():
                if value in [None, ""]:
                    raise ConfigurationError(f"Missing environment variable: {key}")

        except Exception as e:
            raise ConfigurationError(f"Error reading environment variables: {e}") from e

    def connect(self) -> None:
        """
        Establishes a connection to the PostgreSQL database using loaded parameters.

        Raises:
            ConnectionError: If an error occurs during connection.
        """
        try:
            self.connection = psycopg2.connect(
                user=self.database_params['user'],
                password=self.database_params['password'],
                host=self.database_params['host'],
                port=self.database_params['port'],
                database=self.database_params['database']
            )
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as conn_err:
            raise ConnectionError(f"Database connection failed: {conn_err}") from conn_err
        except Exception as e:
            raise ConnectionError(f"Unexpected error during database connection: {e}") from e

    def execute(self, query: str, params: Optional[dict] = None) -> List[Any]:
        """
        Executes a SQL query. SELECT queries and any query with RETURNING return results as list of dicts; 
        other queries commit changes.

        Args:
            query (str): The SQL query to execute.
            params (dict, optional): Parameters to pass to the query.

        Returns:
            List[Any]: The results of the SELECT or RETURNING query; empty list for non-returning queries.

        Raises:
            ConnectionError: If there's a database connection issue.
            SqlSyntaxError: If the query has a syntax error.
            QueryExecutionError: For any other execution error.
        """
        if not isinstance(query, str):
            query = str(query)

        if not self.connection:
            self.connect()

        cursor = None
        results = []

        try:
            cursor = self.connection.cursor(cursor_factory=RealDictCursor)
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            query_lower = query.strip().lower()

            if query_lower.startswith("select"):
                results = cursor.fetchall()
            elif query_lower.startswith("insert") and "returning" in query_lower:
                results = cursor.fetchall()  # <- 🔧 CAPTURA O RETURNING
                self.commit()
            else:
                self.commit()
                results = []

        except (psycopg2.OperationalError, psycopg2.InterfaceError) as conn_err:
            raise ConnectionError(f"Database connection failed: {conn_err}") from conn_err

        except psycopg2.ProgrammingError as syntax_err:
            raise SqlSyntaxError(syntax_err, query)

        except Exception as e:
            raise QueryExecutionError(f"Unexpected error executing query: {e}", query) from e

        finally:
            if cursor:
                cursor.close()
            self.disconnect()

        return results

    def columns(self, table: str) -> List[str]:
        """
        Retrieves the column names of a given table.

        Args:
            table (str): The name of the database table.

        Returns:
            List[str]: A list of column names.

        Raises:
            PgsqlError: If there is an issue fetching the columns.
        """
        if not self.connection:
            self.connect()

        cursor = None
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"SELECT * FROM {table} LIMIT 0")
            return [desc[0] for desc in cursor.description]
        except (psycopg2.DatabaseError, Exception) as error:
            raise QueryExecutionError(f"Error fetching columns from table '{table}': {error}", query=f"SELECT * FROM {table} LIMIT 0")
   
        finally:
            if cursor:
                cursor.close()
            self.disconnect()

    def commit(self) -> None:
        """
        Commits the current transaction.

        Raises:
            QueryExecutionError: If the commit operation fails.
        """
        if self.connection:
            try:
                self.connection.commit()
            except psycopg2.DatabaseError as error:
                raise QueryExecutionError(f"Error committing transaction: {error}", query="COMMIT") from error

    def disconnect(self) -> None:
        """
        Closes the current database connection if it's open.

        Raises:
            ConnectionError: If the disconnection fails.
        """
        if self.connection:
            try:
                self.connection.close()
            except psycopg2.DatabaseError as error:
                raise ConnectionError(f"Error closing the database connection: {error}") from error
            finally:
                self.connection = None