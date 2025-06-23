# exceptions.py

class DaoError(Exception):
    """Base class for all DAO-related exceptions."""
    pass

class MissingParameterError(DaoError):
    """Raised when a required parameter for a dynamic query is missing."""
    def __init__(self, param_name: str):
        message = f"Missing required parameter: <{param_name}>"
        super().__init__(message)
        self.param_name = param_name

class ConnectionError(DaoError):
    """Raised when a connection to the database fails."""
    def __init__(self, original_exception: Exception):
        message = f"Database connection failed: {original_exception}"
        super().__init__(message)
        self.original_exception = original_exception

class SqlSyntaxError(DaoError):
    """Raised when there is a syntax error in the SQL query."""
    def __init__(self, original_exception: Exception, query: str):
        message = f"SQL syntax error: {original_exception}\nQuery: {query}"
        super().__init__(message)
        self.original_exception = original_exception
        self.query = query

class QueryExecutionError(DaoError):
    """Raised for general query execution errors."""
    def __init__(self, original_exception: Exception, query: str = None):
        message = f"Query execution failed: {original_exception}\nQuery: {query}"
        super().__init__(message)
        self.original_exception = original_exception
        self.query = query
    
class RegisterNotFoundError(DaoError):
    """Raised when no register is found for a given DTO."""
    def __init__(self, dto):
        self.dto = dto
        super().__init__(f"No register found matching: {dto}")

class DtoExpectedError(Exception):
    """Raised when an object is not a valid subclass instance of Dto."""
    pass

class DtoMissingAssignedFieldsError(DaoError):
    """Raised when a Dto instance does not have any assigned fields for filtering operations."""
    def __init__(self, dto):
        message = f"DTO instance of type '{type(dto).__name__}' has no assigned fields for filtering."
        super().__init__(message)
        self.dto = dto

class DtoMappingError(DaoError):
    """Raised when mapping a database row to a DTO fails."""
    def __init__(self, message: str):
        super().__init__(f"DTO mapping error: {message}")
        
class ConfigurationError(Exception):
    """Raised when configuration loading fails."""

    def __init__(self, message: str, source: str = None):
        full_message = f"Configuration error: {message}"
        if source:
            full_message += f" (source: {source})"
        super().__init__(full_message)
        self.source = source

class SaveOperationError(Exception):
    """
    Raised when the save operation fails unexpectedly.

    This exception indicates that an attempt to insert a new register into the database failed,
    even after passing the duplicate-check logic. It is triggered when the save() operation could 
    not complete successfully due to unexpected reasons such as DB integrity constraints, 
    connection issues, or other failures during persistence.

    Attributes:
        dto -- The DTO object that was attempted to be saved
        message -- Optional additional error message
    """

    def __init__(self, dto, message="Failed to save register into database."):
        self.dto = dto
        self.message = message
        super().__init__(f"{message} DTO: {dto}")

class UpdateOperationError(DaoError):
    """
    Exception raised when a domain update operation fails.

    This exception is triggered when the ORM attempts to update an existing record but encounters 
    unexpected errors such as:

    - Database execution failure.
    - Update did not affect any rows (record may not exist).
    - Any underlying DAO or SQL-related errors.

    Attributes:
        dto (Dto): The DTO object being updated at the time of failure.
        message (str): The error message.

    Example:
        >>> raise UpdateOperationError(dto=my_dto)
    """

    def __init__(self, dto=None, message="Update operation failed"):
        super().__init__(message)
        self.dto = dto

    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} | DTO: {self.dto}"

class DomainValidationError(Exception):
    """Raised when Domain operation violates declared restrictions."""
    pass

class DomainConstraintError(Exception):
    """
    Raised when a domain-level business constraint is violated.

    Examples:
        - Mutually exclusive parameters are both set.
        - Required relationship inconsistency (e.g., WorkGroup not belonging to Company).
    """
    def __init__(self, message: str):
        super().__init__(f"[DomainConstraintError] {message}")

# exceptions_base.py (ou onde você já centraliza as suas exceções)

class InvalidDomainReferenceError(TypeError):
    def __init__(self, expected_class, received_object):
        super().__init__(
            f"Expected instance of {expected_class.__name__}, "
            f"but received: {type(received_object).__name__}"
        )