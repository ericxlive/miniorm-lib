import json
import uuid

from miniorm.reflection_base import MutableObject, ReflectionUtils

class Dto (MutableObject):
    """
    Base class for Data Transfer Objects (DTOs) with dynamic attribute handling.

    This class extends `MutableObject`, allowing for flexible instantiation and deep updates.
    Attributes can be assigned dynamically via keyword arguments. It is commonly used to
    represent structured data from database queries or JSON payloads in a way that supports
    introspection, serialization, and partial updates.

    Inherits:
        MutableObject: Enables dynamic attributes and deep update support.
    """
    
    def __init__(self, **kwargs):
        """
        Initializes the DTO with dynamic attributes, applying type-tolerant UUID parsing.

        Automatically converts `id` field to UUID if a valid UUID string is provided,
        while maintaining compatibility with int IDs.

        Args:
            **kwargs: Arbitrary keyword arguments representing attribute names and values.

        Example:
            >>> dto = Dto(id="5e10be4f-3e48-450a-baad-94e77a4296b4", name="Alice")
            >>> type(dto.id)
            <class 'uuid.UUID'>
        """
        id_value = kwargs.get("id", None)

        if isinstance(id_value, uuid.UUID):
            kwargs["id"] = id_value
        elif isinstance(id_value, str):
            try:
                kwargs["id"] = uuid.UUID(id_value)
            except ValueError:
                kwargs["id"] = id_value  # Keep original string if not valid UUID
        else:
            kwargs["id"] = id_value

        super().__init__(**kwargs)
    
    def update(self, data: dict):
        """
        Performs a deep update of the DTO instance using the provided dictionary.

        This method recursively updates the attributes of the current DTO object. If an attribute 
        already exists and is itself an object, and the corresponding value in the dictionary is 
        also a dictionary, a deep update is applied to the nested object instead of replacing it.

        This is useful for applying partial updates from deserialized JSON objects without 
        overwriting entire nested structures.

        Args:
            data (dict): A dictionary containing new values for the attributes of the DTO.

        Example:
            >>> dto = UserDto(id=1, profile=ProfileDto(city="Old"))
            >>> dto.update({"profile": {"city": "New"}})
            >>> dto.profile.city
            'New'
        """
        def deep_update(obj, updates):
            for key, value in updates.items():
                if hasattr(obj, key):
                    current_attr = getattr(obj, key)
                    # Se for um objeto e o novo valor é um dicionário, atualiza recursivamente
                    if hasattr(current_attr, '__dict__') and isinstance(value, dict):
                        deep_update(current_attr, value)
                    else:
                        setattr(obj, key, value)
                else:
                    setattr(obj, key, value)

        deep_update(self, data)

    def vars(self):
        """
        Returns a dictionary of the DTO's instance attributes, excluding internal fields.

        This method overrides the base `Object.vars()` to automatically exclude attributes 
        that are commonly used for metadata or infrastructure purposes (such as table name 
        and DAO bindings), making it more suitable for serialization or inspection.

        Returns:
            dict: A dictionary containing only the relevant DTO attributes.
        
        Example:
            >>> dto = UserDto(id=1, name="Alice")
            >>> dto.vars()
            {'id': 1, 'name': 'Alice'}
        """
        return super().vars(ignore=['table', 'dao', '__dao__', 'dto', '__dto__'])
    
    def columns(self, ignore=None, assigned_only=False):
        """
        Returns a dictionary of attribute names and values to be treated as database columns.

        This method filters out internal or infrastructural attributes by default, and optionally
        includes only those that have been explicitly assigned (i.e., not None).

        UUID normalization:
            - If an attribute is a UUID object, it will be automatically converted into its string representation.

        Args:
            ignore (list, optional): A list of attribute names to exclude. Defaults to
                ['dao', 'dto', '__dao__', '__dto__', 'table'].
            assigned_only (bool): If True, only includes attributes with non-None values.
                - Zero (0) and False (boolean) are considered valid assigned values.
                - If False, all attributes not in `ignore` are returned.

        Returns:
            dict: A dictionary mapping column names to their respective values.

        Example:
            >>> import uuid
            >>> dto = UserDto(id=uuid.uuid4(), name=None, is_active=False)
            >>> dto.columns(assigned_only=True)
            {'id': '550e8400-e29b-41d4-a716-446655440000', 'is_active': False}
        """
        if ignore is None:
            ignore = ['dao', 'dto', '__dao__', '__dto__', 'table']

        result = {}
        for k, v in vars(self).items():
            if k in ignore:
                continue

            if assigned_only:
                if v is not None or v is False or v == 0:
                    result[k] = str(v) if isinstance(v, uuid.UUID) else v
            else:
                result[k] = str(v) if isinstance(v, uuid.UUID) else v

        return result

    def __str__(self):
        """
        Returns a JSON-formatted string representation of the DTO, including nested objects.

        This method uses `ReflectionUtils.obj_to_dict` to recursively serialize the object's
        attributes, excluding internal or auxiliary attributes such as 'table', 'dao', '__dao__',
        'dto', and '__dto__'. Useful for printing or exporting structured object data.

        Returns:
            str: A human-readable JSON-formatted string of the object's state.

        Example:
            >>> print(dto)
            {
                "id": 1,
                "name": "Alice",
                "address": {
                    "city": "New York"
                }
            }
        """
        def default_serializer(o):
            if isinstance(o, uuid.UUID):
                return str(o)
            return str(o)
            
        return json.dumps(
            ReflectionUtils.obj_to_dict(
                self, 
                ignore=['table', 'dao', '__dao__', 'dto', '__dto__']
            ), 
            indent=4,
            default=default_serializer
        )
    
    def __repr__(self):
        """
        Returns the official string representation of the object for debugging and logging.

        Delegates to the `__str__` method to provide a detailed JSON-formatted output
        that includes nested structures, making it suitable for inspection in logs
        and interactive sessions.

        Returns:
            str: JSON-formatted string representation of the DTO instance.
        """
        return self.__str__()