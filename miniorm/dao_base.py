
from datetime import datetime, time
from miniorm.sql_utils import sql_value

from miniorm.exceptions_base import (
    ConnectionError,
    SqlSyntaxError,
    QueryExecutionError,
    DtoMappingError,
    MissingParameterError,
    RegisterNotFoundError,
    DtoMissingAssignedFieldsError
)
from miniorm.sql_utils import sql_escape
from miniorm.dto_base import Dto
from miniorm.utilities_base import log
from miniorm.pgsql import Pgsql
from miniorm.exceptions_base import *
from miniorm.reflection_base import *

class Dao:
    
    """
    Base Data Access Object (DAO) class that abstracts SQL operations for DTO-based persistence.

    The Dao layer is fully decoupled from the Domain layer. It only works directly with DTOs
    (Data Transfer Objects) which represent flat structures of database tables.

    Responsibilities:
    - Execute SELECT, INSERT, and JOIN queries using PostgreSQL (via Pgsql helper).
    - Map query results into instances of DTO classes.
    - Validate DTO types and assigned fields.
    - Handle SQL generation, filtering, parameterization, and connection management.
    - Raise consistent exceptions for common database and mapping errors.

    Limitations:
    - Does not support foreign key resolution or nested object mappings.
    - All foreign key encapsulation and nested domain enrichment is handled exclusively 
    at the Domain layer.

    Usage example:
        >>> dao = Dao(model=ContractDto)
        >>> dto = ContractDto(member_id=3)
        >>> results = dao.find_all(dto)
        >>> for r in results:
        ...     print(r.id, r.member_id, r.company_id)

    Attributes:
        model (Type[Dto]): The DTO class handled by this DAO instance.
        db (Pgsql): The database connection manager used for executing SQL queries.
    """

    def __init__(self, model, db=None):
        """
        Initializes a new Dao instance.

        Args:
            model (Type[Dto]): The DTO class associated with this DAO.
            db (Pgsql, optional): An optional database connection instance.
                                  If not provided, a default Pgsql instance is used.
        """
        self.model = model
        self.db = db or Pgsql()

    def list(self):
        """
        Retrieves all records from the database table associated with this DAO, without applying any filters.

        Unlike `find_all()` which requires a DTO with assigned fields for filtering, this method simply
        selects all rows in the corresponding table and maps them into DTO instances.

        This method is particularly useful for:
        - Full data loads
        - Admin interfaces
        - Debugging and inspection
        - Export operations

        Returns:
            list: A list of DTO instances, one per row in the table.

        Raises:
            ConnectionError: If the database connection fails.
            SqlSyntaxError: If the generated SQL contains syntax errors.
            QueryExecutionError: If execution of the SQL fails.
            DtoMappingError: If mapping the result to DTO instances fails.

        Example:
            >>> dao = CompanyDao()
            >>> all_companies = dao.list()
            >>> for company in all_companies:
            ...     print(company.name)
        """
        try:
            db = Pgsql()
        except Exception as e:
            raise ConnectionError(e)

        try:
            valid_columns = db.columns(self.model().table)
            query = f"SELECT {', '.join(valid_columns)} FROM {self.model().table}"
            log(query=query)
            rows = db.execute(query)

            results = []
            for row in rows:
                try:
                    instance = ReflectionUtils.new_instance(self.model())
                    instance.sync(row)
                    results.append(instance)
                except Exception as e:
                    raise DtoMappingError(f"Failed to map row to DTO: {e}") from e

            db.disconnect()
            return results

        except SyntaxError as e:
            raise SqlSyntaxError(e, query)
        except Exception as e:
            raise QueryExecutionError(e, query)

    def find_all(self, dto=None):
        """
        Fetches rows from the database table corresponding to the provided DTO,
        applying filters based on assigned fields in the DTO.

        If no DTO is provided, all records from the corresponding table are returned.

        Args:
            dto (Dto, optional): An instance of a DTO subclass containing filters and metadata.
                                If omitted, fetches all records.

        Returns:
            list: A list of populated DTO instances.

        Raises:
            DtoExpectedError: If the input is not a valid Dto subclass instance.
            ConnectionError: If the database connection fails.
            SqlSyntaxError: If the generated SQL contains syntax errors.
            QueryExecutionError: If execution of the SQL fails.
            DtoMappingError: If mapping the result to DTO instances fails.
        """
        if dto is None:
            dto = self.model()

        if not isinstance(dto, Dto) or type(dto) is Dto:
            raise DtoExpectedError(f"Expected a subclass instance of Dto, got {type(dto).__name__}")

        try:
            db = Pgsql()
        except Exception as e:
            raise ConnectionError(e)

        try:
            valid_columns = db.columns(dto.table)
            select_columns = [k for k in dto.columns().keys() if k in valid_columns]

            filters = []
            for k, v in dto.columns(assigned_only=True).items():
                if k in valid_columns and v is not None:
                    if isinstance(v, (bool, int, float)):
                        filters.append(f"{k} = {v}")
                    elif isinstance(v, uuid.UUID):
                        filters.append(f"{k} = '{str(v)}'")
                    else:
                        filters.append(f"{k} = '{sql_escape(str(v))}'")

            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            query = f"SELECT {', '.join(select_columns)} FROM {dto.table}{where_clause}"

            log(query=query)
            rows = db.execute(query)

        except SyntaxError as e:
            raise SqlSyntaxError(e, query)
        except Exception as e:
            raise QueryExecutionError(e, query)

        results = []
        for row in rows:
            try:
                instance = ReflectionUtils.new_instance(dto.model())
                instance.sync(row)
                results.append(instance)
            except Exception as e:
                raise DtoMappingError(f"Failed to map row to DTO: {e}") from e

        return results

    def _find_all(self, dto):
        """
        Fetches rows from the database table corresponding to the provided DTO,
        applying filters based on assigned fields in the DTO.

        This method only works with flat DTOs. Nested object encapsulation and
        foreign key mappings are entirely handled at the Domain layer, not here.

        Args:
            dto (Dto): An instance of a DTO subclass containing filters and metadata
                    like the target table and associated model.

        Returns:
            list: A list of populated DTO instances.

        Raises:
            DtoExpectedError: If the input is not a valid Dto subclass instance.
            DtoMissingAssignedFieldsError: If no fields are assigned in the given dto.
            ConnectionError: If the database connection fails.
            SqlSyntaxError: If the generated SQL contains syntax errors.
            QueryExecutionError: If execution of the SQL fails.
            DtoMappingError: If mapping the result to DTO instances fails.

        Example:
            >>> dto = ContractDto(member_id=3)
            >>> dao = Dao(model=ContractDto)
            >>> results = dao.find_all(dto)
            >>> for r in results:
            ...     print(r.member_id)
        """
        if not isinstance(dto, Dto) or type(dto) is Dto:
            raise DtoExpectedError(f"Expected a subclass instance of Dto, got {type(dto).__name__}")

        if not dto.columns(assigned_only=True):
            raise DtoMissingAssignedFieldsError(dto)

        try:
            db = Pgsql()
        except Exception as e:
            raise ConnectionError(e)

        try:
            valid_columns = db.columns(dto.table)
            select_columns = [k for k in dto.columns().keys() if k in valid_columns]

            filters = []
            for k, v in dto.columns(assigned_only=True).items():
                if k in valid_columns and v is not None:
                    if isinstance(v, (bool, int, float)):
                        filters.append(f"{k} = {v}")
                    elif isinstance(v, uuid.UUID):
                        filters.append(f"{k} = '{str(v)}'")
                    else:
                        filters.append(f"{k} = '{sql_escape(str(v))}'")

            where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""
            query = f"SELECT {', '.join(select_columns)} FROM {dto.table}{where_clause}"

            log(query=query)
            rows = db.execute(query)

        except SyntaxError as e:
            raise SqlSyntaxError(e, query)
        except Exception as e:
            raise QueryExecutionError(e, query)

        results = []
        for row in rows:
            try:
                instance = ReflectionUtils.new_instance(dto.model())
                instance.sync(row)
                results.append(instance)
            except Exception as e:
                raise DtoMappingError(f"Failed to map row to DTO: {e}") from e

        return results
    
    def joint_find(self, query: str, dto_model, **params):
        """
        Executes a parameterized SQL query and maps the result rows into instances of the specified DTO model.

        Args:
            query (str): The SQL query string using <param> placeholders.
            dto_model (type): The DTO class to map the result rows into.
            **params: Parameters for substitution in the query. All values are safely escaped.

        Returns:
            list: A list of DTO instances populated with data from the query.

        Raises:
            MissingParameterError: If a required query parameter is missing.
            ConnectionError: If the database connection fails.
            SqlSyntaxError: If the SQL query contains syntax errors.
            QueryExecutionError: For any other query execution issues.
            DtoMappingError: If mapping a row to a DTO fails.
        """
        try:
            # Replace <param> with %(param)s and validate that all are provided
            for key in params:
                placeholder = f'<{key}>'
                if placeholder in query:
                    query = query.replace(placeholder, f'%({key})s')

            # Check for unfilled placeholders
            import re
            missing = re.findall(r'<(\w+)>', query)
            if missing:
                raise MissingParameterError(missing[0])

            # Normalize NULL comparisons
            query = query.replace('= null', 'IS NULL').replace('=null', 'IS NULL')

            # Connect and execute
            try:
                db = Pgsql()
            except Exception as e:
                raise ConnectionError(e)

            try:
                log(query=query, params=params)
                rows = db.execute(query, params)  # Already returns list of dicts
            except SyntaxError as e:
                raise SqlSyntaxError(e, query)
            except Exception as e:
                raise QueryExecutionError(e, query)

            results = []
            for row in rows:
                json_obj = {}
                for col_name, value in row.items():
                    if isinstance(value, datetime):
                        value = value.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(value, time):
                        value = value.strftime("%H:%M")
                    elif hasattr(value, 'strftime'):
                        value = value.strftime("%Y-%m-%d")
                    elif isinstance(value, str):
                        # Attempt auto UUID parsing
                        try:
                            value = uuid.UUID(value)
                        except (ValueError, TypeError):
                            pass
                    json_obj[col_name] = value

                try:
                    instance = ReflectionUtils.new_instance(dto_model)
                    instance.sync(json_obj)
                    results.append(instance)
                except Exception as e:
                    raise DtoMappingError(f"Failed to map row to DTO: {e}") from e

            db.disconnect()
            return results

        except DaoError:
            raise  # Let known exceptions bubble up
        except Exception as e:
            raise QueryExecutionError(e, query)
    
    def find_one(self, dto, raise_if_not_found=False):
        """
        Attempts to find a single register in the database matching the given DTO's assigned fields.

        Args:
            dto: An instance of a DTO with assigned filter fields.
            raise_if_not_found (bool): If True, raises RegisterNotFoundError when no match is found.

        Returns:
            The single DTO instance if exactly one match is found; otherwise, None or raises error.

        Raises:
            RegisterNotFoundError: If no matching register is found and `raise_if_not_found=True`.
            QueryExecutionError: If there is an issue executing the underlying query.
            DtoMappingError: If a record could not be mapped to the DTO.
        """
        if not isinstance(dto, Dto) or type(dto) is Dto:
            raise DtoExpectedError(f"Expected a subclass instance of Dto, got {type(dto).__name__}")

        try:
            results = self.find_all(dto=dto)

            if not results:
                if raise_if_not_found:
                    raise RegisterNotFoundError(dto)
                return None

            if len(results) > 1:
                log(f"[WARN] find_one() expected 1 result but got {len(results)}")
                return None

            return results[0]

        except DaoError:
            raise
        except Exception as e:
            raise QueryExecutionError(e)
        
    def exists(self, dto):
        """
        Checks whether a record matching the provided DTO exists in the database.

        This method uses the DTO's assigned fields as filters to perform a lookup via `find_one`.
        If a record matching those fields is found, the method returns True.

        Args:
            dto (Dto): An instance of a subclass of Dto with one or more fields set as filters.

        Returns:
            bool: True if a matching record exists, False otherwise.

        Raises:
            DtoExpectedError: If the provided object is not a subclass instance of Dto.
            DtoMissingAssignedFieldsError: If no filterable fields are set on the DTO.
            ConnectionError, SqlSyntaxError, QueryExecutionError, DtoMappingError: As raised by find_one.
        """
        if not isinstance(dto, Dto) or type(dto) is Dto:
            raise DtoExpectedError(f"Expected an instance of a subclass of Dto, got {type(dto).__name__}")

        if not dto.columns(assigned_only=True):
            raise DtoMissingAssignedFieldsError("DTO must have at least one assigned field to check for existence.")

        obj = self.find_one(dto=dto)
        return bool(obj)

    def save(self, dto):
        """
        Inserts a new record into the database using the data from the given DTO,
        and updates the DTO with the newly generated ID (if applicable).

        Args:
            dto (Dto): An instance of a subclass of Dto representing the data to be inserted.

        Returns:
            bool: True if the operation succeeds, False otherwise.

        Raises:
            DtoExpectedError: If the provided object is not a subclass instance of Dto.
            ConnectionError: If the database connection fails.
            SqlSyntaxError: If the SQL statement has a syntax error.
            QueryExecutionError: For any other unexpected execution issues.
        """
        if not isinstance(dto, Dto) or type(dto) is Dto:
            raise DtoExpectedError(f"Expected an instance of a subclass of Dto, got {type(dto).__name__}")

        def sql_escape(value: str) -> str:
            return value.replace("'", "''")

        columns = {}
        for k, v in dto.columns().items():
            if k == 'id':
                continue
            if v is not None:
                if isinstance(v, uuid.UUID):
                    columns[k] = f"'{str(v)}'"
                elif isinstance(v, (int, float, bool)):
                    columns[k] = str(v)
                else:
                    columns[k] = f"'{sql_escape(str(v))}'"

        query = (
            f"INSERT INTO {dto.table} ({', '.join(columns.keys())}) "
            f"VALUES ({', '.join(columns.values())}) RETURNING id"
        )
        log(query=query)

        try:
            db = Pgsql()
        except Exception as e:
            raise ConnectionError(e)

        try:
            rows = db.execute(query=query)

            if rows and isinstance(rows[0], dict) and 'id' in rows[0]:
                returned_id = rows[0]['id']
                if isinstance(returned_id, str):
                    try:
                        returned_id = uuid.UUID(returned_id)
                    except ValueError:
                        pass  # mantém string se não for UUID válido
                dto.id = returned_id
            else:
                dto.id = None  # fallback seguro
            db.disconnect()
            return True
        except SyntaxError as e:
            raise SqlSyntaxError(e, query)
        except Exception as e:
            raise QueryExecutionError(e, query)
        
    def update(self, dto):
        """
        Updates an existing record in the database using the data from the given DTO.

        Args:
            dto (Dto): An instance of a subclass of Dto representing the data to be updated.
                    The 'id' field must be assigned to identify the target record.

        Returns:
            bool: True if the operation succeeds, False otherwise.

        Raises:
            DtoExpectedError: If the provided object is not a subclass instance of Dto.
            ConnectionError: If the database connection fails.
            SqlSyntaxError: If the SQL statement has a syntax error.
            QueryExecutionError: For any other unexpected execution issues.
        """
        
        if not isinstance(dto, Dto) or type(dto) is Dto:
            raise DtoExpectedError(f"Expected an instance of a subclass of Dto, got {type(dto).__name__}")

        if dto.id is None:
            raise DtoMissingAssignedFieldsError("DTO must have 'id' assigned for update operation.")

        # Build SET clause using sql_value()
        vars_dict = dto.columns(assigned_only=False)
        set_clauses = [f"{k} = {sql_value(v)}" for k, v in vars_dict.items() if k != 'id']
        set_clause_str = ', '.join(set_clauses)
        id_value = sql_value(dto.id)

        query = f"UPDATE {dto.table} SET {set_clause_str} WHERE id = {id_value}"
        log(query=query)

        try:
            db = Pgsql()
        except Exception as e:
            raise ConnectionError(e)

        try:
            db.execute(query=query)
            db.disconnect()
            return True
        except SyntaxError as e:
            raise SqlSyntaxError(e, query)
        except Exception as e:
            raise QueryExecutionError(e, query)