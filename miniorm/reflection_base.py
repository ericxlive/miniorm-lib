
import re
import uuid

'''Every class is to be considered a subclass of Object to access Reflection support.'''    
class Object:
    """
    Base class for all objects that require reflection-based utilities and dynamic behavior.

    This class is designed to be inherited by domain models or other classes 
    that need features such as runtime inspection, synchronization between 
    objects, and metadata access.

    It provides foundational behavior to enable:
    - Reflection-based synchronization between objects or dictionaries
    - Metadata discovery (e.g., fully qualified class name)
    - Consistent structure across domain-level objects

    Intended to be extended, not used directly.
    """
    
    def __init__(self):
        pass

    def vars(self, ignore=[]):
        """
        Returns a dictionary of the instance's attributes, excluding any specified in the ignore list.

        This is a convenience wrapper around `ReflectionUtils.vars`, allowing you to call `self.vars()` 
        directly from any object that inherits from this base class.

        Args:
            ignore (list, optional): A list of attribute names to exclude from the result. Defaults to an empty list.

        Returns:
            dict: A dictionary containing the object's attributes, excluding the ignored ones.

        Example:
            >>> class Person(Object):
            ...     def __init__(self):
            ...         self.name = "Alice"
            ...         self.age = 30
            >>> p = Person()
            >>> p.vars(ignore=['age'])
            {'name': 'Alice'}
        """
        return ReflectionUtils.vars(self, ignore=ignore)

    """
    Returns the fully qualified name (FQN) of the class, including its module path.

    This is useful for reflection, logging, debugging, or dynamic class loading, 
    as it provides a unique string identifier for the class in the format: 
    `module_name.ClassName`.

    Returns:
        str: A string representing the absolute module path and class name, 
        e.g., 'app.models.User'.
    """
    @classmethod
    def model(cls):
        members = [type(cls()).__module__, cls.__name__]
        return '.'.join(members)
    
    """
    Synchronizes the current object's attributes with those from another object or dictionary.

    This method performs a field-by-field assignment from the source object or dictionary 
    to the current instance (`self`). Only attribute names that exist in the current 
    object will be updated. Attributes not found in the current instance are ignored.

    If the source is a dictionary, it will synchronize keys and values directly.
    If the source is an object, it will copy matching attributes.

    Args:
        obj (object or dict): The source from which to copy data.
        ignore_private (bool): If True, attributes that start with an underscore (_) 
                               will be ignored during synchronization. Default is False.

    Returns:
        self: The current instance, updated with the source data.

    Use case:
        - Updating domain objects from database records, DTOs, or raw JSON data.
        - Keeping object state in sync during transformations.
    """
    def sync(self, obj, ignore_private=False):
        if isinstance(obj, dict): 
            ReflectionUtils.sync_with_dict(to_obj=self, dict=obj, ignore_private=ignore_private)
        else: 
            ReflectionUtils.sync_objects(to_obj=self, from_obj=obj, ignore_private=ignore_private)
        return self

class MutableObject(Object):
    """
    Subclass of `Object` that allows dynamic attribute creation via named parameters
    and supports deep updates with nested dictionaries.

    This class is useful for creating flexible instances with variable attributes or
    updating objects recursively based on JSON/dictionary structures.

    Key features:
    - Initialization using `**kwargs`, directly assigning attributes.
    - `update()` method that performs recursive (deep) updates of attributes, including nested objects.
    """

    def __init__(self, **kwargs):
        """
        Constructor that accepts dynamic attributes via keyword arguments.

        Each key-value pair is directly assigned as an instance attribute.

        Args:
            **kwargs: Dynamic attributes to be defined on the object.
        """
        super().__init__()
        for key, value in kwargs.items():
            setattr(self, key, value)

    def update(self, data: dict):
        """
        Updates the instance's attributes with values provided in a dictionary.

        The update is deep: if a current attribute is an object and the corresponding value 
        in the dictionary is also a dictionary, the update will recursively apply to the 
        nested object's attributes.

        Args:
            data (dict): Dictionary containing data to apply to the instance.

        Use cases:
            - Updating complex objects from decoded JSON.
            - Applying dynamic changes without overwriting nested objects.
        """
        def deep_update(obj, updates):
            for key, value in updates.items():
                if hasattr(obj, key):
                    current_attr = getattr(obj, key)
                    if hasattr(current_attr, '__dict__') and isinstance(value, dict):
                        # Recursive update on nested objects
                        deep_update(current_attr, value)
                    else:
                        setattr(obj, key, value)
                else:
                    setattr(obj, key, value)

        deep_update(self, data)
        
'''Clean Shell class to be used. No other method to be added. This class is just to 
   encapsulate others class objects in order to display the objects in a JSON format.'''
class Shell(MutableObject):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

'''Reflection based functions.'''
class ReflectionUtils:
    """
    Utility class for reflection-based operations.

    This class provides static methods to synchronize attributes between
    objects or between dictionaries and objects. It is designed to be 
    non-instantiable and non-extendable.
    """

    # The constructor is not available. If called it will not work propery.
    __new__ = __init__ = None

    @staticmethod
    def sync_objects(to_obj, from_obj, add_attr=True, ignore_private=False):
        """
        Synchronizes attributes from one object to another.

        Copies all attributes from `from_obj` to `to_obj`. If `add_attr` is True,
        attributes that exist in `from_obj` but not in `to_obj` will be added. 
        If False, only existing attributes in `to_obj` will be updated.

        Args:
            to_obj (object): The object that will receive the attributes.
            from_obj (object): The object whose attributes will be copied.
            add_attr (bool): Whether to add new attributes to `to_obj` 
                             if they don't already exist. Default is True.
            ignore_private (bool): If True, attributes starting with an underscore 
                                   (`_`) will be ignored. Default is False.

        Example:
            class A: pass
            class B: pass

            a = A(); b = B()
            b.foo = 1
            ReflectionUtils.sync_objects(a, b)

        Note:
            Only attributes in `from_obj.__dict__` are considered.
        """
        kwargs = vars(from_obj)
        keys = vars(to_obj).keys()
        for k, v in kwargs.items():
            if ignore_private and k.startswith('_'):
                continue
            if add_attr or k in keys:
                setattr(to_obj, k, v)

    @staticmethod
    def looks_like_uuid(value):
        """
        Checks if a given value is a string that matches the format of a UUID.

        Args:
            value (any): The value to check.

        Returns:
            bool: True if value appears to be a UUID string, False otherwise.
        """
        return isinstance(value, str) and re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', value)

    @staticmethod
    def sync_with_dict(to_obj, dict, ignore_private=False):
        """
        Synchronizes object attributes with values from a dictionary.

        Updates attributes of `to_obj` using key-value pairs from the given `dict`.
        Keys in the dictionary become attribute names in the object.
        If an attribute does not exist, it will be created.

        UUID auto-conversion:
            - If the attribute already exists in `to_obj` and is of type `uuid.UUID`, 
            and the provided value is a string, it automatically converts the string 
            into a UUID object (if valid).
            - If the value is already a UUID instance, it is assigned directly.

        Args:
            to_obj (object): The object that will be updated.
            dict (dict): A dictionary with keys as attribute names and values as the data.
            ignore_private (bool): If True, keys starting with an underscore (`_`) 
                                    will be ignored. Default is False.

        Example:
            class User: pass
            u = User()
            ReflectionUtils.sync_with_dict(u, {'name': 'Alice', '_temp': 42}, ignore_private=True)

        Note:
            This method modifies the object in-place.
        """
        for k, v in dict.items():
            if ignore_private and k.startswith('_'):
                continue

            if hasattr(to_obj, k):
                target_attr = getattr(to_obj, k)
                if isinstance(target_attr, uuid.UUID) and isinstance(v, str):
                    try:
                        v = uuid.UUID(v)
                    except ValueError:
                        pass
            else:
                # Handle UUID if the value looks like one and no attribute exists yet
                if ReflectionUtils.looks_like_uuid(v):
                    try:
                        v = uuid.UUID(v)
                    except ValueError:
                        pass
                    
            setattr(to_obj, k, v)

    @staticmethod
    def obj_to_dict(obj, ignore=None, clean_nested_keys=False):
        """
        Recursively converts an object into a dictionary representation,
        supporting nested serialization and optional foreign key cleanup
        for domain objects that declare 'foreign_keys'.

        Args:
            obj (object): The object to convert. Can be a custom class, list, or primitive.
            ignore (list[str], optional): List of attribute names to ignore during conversion.
            clean_nested_keys (bool, optional): If True, removes foreign key fields (e.g., 'member_id')
                                                when nested domain objects are present.

        Returns:
            dict | list | any: A dictionary (or list of dictionaries) representing the object.
        """
        if ignore is None:
            ignore = []

        if hasattr(obj, '__dict__'):
            data = {
                key: ReflectionUtils.obj_to_dict(value, ignore, clean_nested_keys)
                for key, value in obj.__dict__.items()
                if key not in ignore
            }

            # If requested, remove foreign keys if foreign_keys mapping exists
            if clean_nested_keys and hasattr(obj, 'foreign_keys'):
                for fk_field in obj.foreign_keys.keys():
                    if fk_field in data:
                        del data[fk_field]

            return data

        elif isinstance(obj, list):
            return [ReflectionUtils.obj_to_dict(item, ignore, clean_nested_keys) for item in obj]

        else:
            return obj
        
    @staticmethod
    def new_instance(blueprint):
        """
        Dynamically creates and returns a new instance of a class from a fully qualified class name (blueprint).

        This method uses the `pydoc.locate` function to resolve a class from a string path, 
        and then instantiates it. It is useful for scenarios involving dynamic loading of 
        models, services, or other components based on configuration or metadata.

        Args:
            blueprint (str): The fully qualified class path (e.g., 'app.models.User').

        Returns:
            object: A new instance of the resolved class.

        Raises:
            AttributeError: If the class cannot be located or instantiated.

        Example:
            instance = ReflectionUtils.new_instance('myapp.models.Customer')
        """
        from pydoc import locate
        my_class = locate(blueprint)
        instance = my_class()
        return instance
    
    @staticmethod
    def vars(obj, ignore=[]):
        """
        Returns a dictionary of the object's attributes, excluding those specified in the ignore list.

        This method provides a filtered view of the object's internal attributes (those stored in `__dict__`), 
        omitting any attribute whose name appears in the `ignore` list.

        Args:
            obj: The object whose attributes should be retrieved.
            ignore (list, optional): A list of attribute names to exclude from the result. Defaults to an empty list.

        Returns:
            dict: A dictionary containing the object's attributes, excluding the ignored ones.

        Example:
            >>> class Sample:
            ...     def __init__(self):
            ...         self.a = 1
            ...         self.b = 2
            >>> s = Sample()
            >>> ReflectionUtils.vars(s, ignore=['b'])
            {'a': 1}
        """
        result = {}
        members = vars(obj)
        for k, v in members.items():
            if k not in ignore:
                result[k] = v
        return result
    
    # Support to lists [] inside the domain class. It will return a list from related table.
    # Product vs Items. Items hold id of product. So if product is listed it will also hold
    # the items list []
    @staticmethod
    def get_nested_list_metadata(domain_cls):
        metadata = {}
        for attr_name in dir(domain_cls):
            attr = getattr(domain_cls, attr_name, None)
            if callable(attr) and hasattr(attr, "_nested_list"):
                info = attr._nested_list
                metadata[attr_name] = {
                    "class": info["target"],
                    "foreign_key": info["foreign_key"]
                }
        return metadata