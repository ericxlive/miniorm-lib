import json
import uuid

from miniorm.reflection_base import Object, ReflectionUtils
from miniorm.utilities_base import log

from miniorm.exceptions_base import SaveOperationError, UpdateOperationError

from miniorm.validation_base import ValidationObserver, validate

from typing import TypeVar, List

T = TypeVar('T', bound='Domain')

class Domain(Object, ValidationObserver):
    """
    Base class for all domain models that require reflection-based operations.

    Every subclass of `Domain` inherits from `Object`, enabling support for 
    reflection utilities such as dynamic instantiation, attribute inspection, 
    and conversion to DTOs or JSON representations.

    This class serves as a foundational model in the application’s domain layer, 
    providing common functionality and structure for all entities that interact 
    with the reflection system.

    Typical use cases include:
    - Converting instances to dictionaries or JSON
    - Creating DTOs from model instances
    - Ignoring specific metadata fields during serialization
    """
    clean_nested_keys: bool = False # Default for all Domains. Retro compatibility apply.
    
    def __init__(self, **kwargs):
        """
        Initializes a Domain object with full support for dynamic attributes and foreign key auto-binding.

        This constructor fully supports:
            - Regular primitive attributes (e.g. id, name, etc.)
            - Foreign key attributes, passed either as Domain instances or IDs.
            - Full backward compatibility: allows legacy code to continue using member_id / company_id directly.
            - Automatic foreign key binding via internal call to `self.join(**kwargs)`.

        Foreign Key Auto-Binding:
            - If foreign_keys are defined in the Domain subclass, the constructor can automatically
            detect if the corresponding Domain objects were passed (e.g. member=Member(...)).
            - When detected, the constructor extracts the .id and assigns both:
                - The foreign key ID field (e.g. member_id)
                - The full nested Domain object (e.g. member)

        This allows flexible object construction:
            - Using only IDs:
                Enrolment(member_id=5, company_id=3)
            - Using full Domain objects:
                Enrolment(member=Member(id=5), company=Company(id=3))
            - Or mixing both approaches.

        Fluent chaining also becomes possible via join():
            enrolment = Enrolment().join(member=member_obj).join(company=company_obj)

        Args:
            **kwargs: Arbitrary fields (both IDs and/or Domain instances).

        Example usage:
            >>> member = Member(id=5)
            >>> company = Company(id=3)
            >>> enrolment = Enrolment(member=member, company=company)
        """
        super().__init__()
        self.join(**kwargs)

        # Patch: Tuple-style foreign_keys (e.g., 'caller_id': ('member', 'Member'))
        '''
        for fk_field, mapping in getattr(self.__class__, 'foreign_keys', {}).items():
            if isinstance(mapping, tuple):
                nested_attr, _ = mapping
                nested_obj = kwargs.get(nested_attr)
                if nested_obj:
                    # Tentativa: usar field name exato (ex: 'caller_id') ou fallback para .id
                    value = getattr(nested_obj, fk_field, None) or getattr(nested_obj, 'id', None)
                    if value:
                        setattr(self, fk_field, value)
        '''
        # Patch: Tuple-style foreign_keys (e.g., 'caller_id': ('member', 'Member', 'caller_id'))
        for fk_field, mapping in getattr(self.__class__, 'foreign_keys', {}).items():
            if isinstance(mapping, tuple):
                nested_attr = mapping[0]
                lookup_field = mapping[2] if len(mapping) > 2 else fk_field  # usa o 3º se existir, senão usa o próprio fk_field

                nested_obj = kwargs.get(nested_attr)
                if nested_obj:
                    value = getattr(nested_obj, lookup_field, None)
                    if value:
                        setattr(self, fk_field, value)
        # /Patch

        # /Patch

    def join(self, **kwargs):
        """
        Fluent interface for assigning foreign key relations dynamically.

        This method allows passing related domain objects directly as arguments, 
        and it will automatically extract their IDs and assign *_id fields accordingly.

        - If the domain class declares foreign_keys, nested domain objects will also be assigned.
        - If the domain class does not declare foreign_keys, only *_id fields will be assigned.

        This enables both:
        - Flat relations (for simple ID-based filtering)
        - Rich nested relations (for full encapsulation, if foreign_keys are declared)

        Args:
            kwargs: keyword arguments where keys can be normal fields or foreign key domains.

        Example:
            >>> contract = Contract().join(member=member_obj, company=company_obj).find()

        Returns:
            self (Domain): fluent interface support.
        """
        foreign_keys = getattr(self.__class__, 'foreign_keys', {})

        for key, value in kwargs.items():
            if isinstance(value, Domain):
                fk_field = f"{key}_id"
                setattr(self, fk_field, value.id)

                if key in foreign_keys:
                    setattr(self, key, value)
            else:
                setattr(self, key, value)

        return self

    '''The function returns the dao previously created. If no dao was created then it will
      create and return the dao instance.'''
    def getdao(self):
       keys = vars(self).keys()
       if '__dao__' in keys:
          if not self.__dao__: 
             self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao) 
          return self.__dao__
       else: 
          self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)
       return self.__dao__

    def as_dto(self):
        """
        Converts the current Domain instance into its corresponding DTO 
        (Data Transfer Object), resolving foreign key objects to *_id fields.

        This method performs the following steps:
        - If foreign key mappings exist, it extracts the `id` from nested domain objects
        (e.g., `company_category.id` → `company_category_id`).
        - It creates a new instance of the DTO class using the declared `self.dto` blueprint.
        - It copies only matching attributes that are defined in the DTO (excluding nested objects),
        ensuring no invalid fields are injected.

        This guarantees that only database-safe fields are passed to INSERT or UPDATE operations.

        Returns:
            object: A fully prepared DTO instance, ready for persistence.
        """
        # Resolve foreign key objects into *_id fields
        if getattr(self, "foreign_keys", None):
            for fk_field, klass in self.foreign_keys.items():
                obj = getattr(self, fk_field.replace('_id', ''), None)
                if obj and hasattr(obj, 'id'):
                    setattr(self, fk_field, obj.id)

        # Ignore @nested_list attributes
        nested_list_fields = ReflectionUtils.get_nested_list_metadata(self.__class__).keys()
        # /Ignore @nested_list attributes

        # Create a fresh DTO instance
        new_obj = ReflectionUtils.new_instance(blueprint=self.dto)

        # Copy only attributes that are defined in the DTO
        dto_fields = vars(new_obj).keys()
        for key, value in vars(self).items():
            # Ignore @nested_list attributes: Added: and key not in nested_list_fields (down below)
            if key in dto_fields and key not in nested_list_fields: 
                setattr(new_obj, key, value)

        return new_obj
    
    def normalize_foreign_keys(self):
        """
        Ensures UUID normalization for the object's own 'id' and for all *_id fields
        defined in foreign_keys, **only if clean_nested_keys is False or undefined**.

        If 'clean_nested_keys' is True, this method skips processing *_id fields,
        assuming that nested objects should take precedence.
        """
        # Normalize own ID
        if hasattr(self, "id") and isinstance(self.id, str):
            try:
                self.id = uuid.UUID(self.id)
            except ValueError:
                pass

        # Skip FK normalization if clean_nested_keys = True
        if getattr(self, "clean_nested_keys", False):
            return

        # Normalize *_id fields from foreign_keys
        if hasattr(self, "foreign_keys"):
            for fk_field in self.foreign_keys.keys():
                if hasattr(self, fk_field):
                    value = getattr(self, fk_field)
                    if isinstance(value, str):
                        try:
                            setattr(self, fk_field, uuid.UUID(value))
                        except ValueError:
                            pass
            
    def encapsulate_nested(self, depth=1):
        from miniorm.lib_explorer import resolve_class_by_name
        """
        Automatically hydrates and assigns nested domain objects based on foreign key mappings.

        This method inspects the `foreign_keys` attribute defined in the domain class (if present),
        and for each mapped foreign key field (e.g., 'member_id'), it dynamically:
            1. Creates the corresponding domain instance (e.g., Member(id=member_id)).
            2. Calls `.find()` on the instance to fully load its data from the database.
            3. Assigns the fully hydrated domain object to a new attribute (e.g., self.member).

        Depth Control:
            - To avoid infinite recursion in case of cyclic or deeply nested foreign keys,
            this method accepts a `depth` parameter.
            - Default depth is 1: only immediate nested objects are hydrated.
            - Each recursive call decrements the depth by 1.

        If no `foreign_keys` attribute exists, or if any foreign key value is None,
        the method skips that mapping gracefully.

        After encapsulation, if clean_nested_keys is enabled, foreign key fields are removed.

        Args:
            depth (int): Maximum recursion depth for nested encapsulation. Default is 1.

        Returns:
            self: The current domain instance, fully hydrated with nested domain objects.
        """
        if depth <= 0:
            return self

        if not hasattr(self.__class__, 'foreign_keys'):
            return self

        from miniorm.log_control import log_suppressed
        with log_suppressed():
            for fk_field, domain_info in self.__class__.foreign_keys.items():
                # Patch: support tuple-style mapping
                if isinstance(domain_info, tuple):
                    # Format: (nested_attr, class_name_or_type, custom_lookup_field)
                    nested_attr = domain_info[0]
                    domain_class = domain_info[1]
                    lookup_field = domain_info[2] if len(domain_info) > 2 else 'id'
                else:
                    nested_attr = fk_field.replace('_id', '')
                    domain_class = domain_info
                    lookup_field = 'id'
                # /Patch

                fk_value = getattr(self, fk_field, None)
                if fk_value is not None:
                    # Patch: resolve class by name if it's a string
                    if isinstance(domain_class, str):
                        domain_class = resolve_class_by_name(domain_class)
                    # /Patch

                    #nested_instance = domain_class(id=fk_value).find()
                    nested_instance = domain_class(**{lookup_field: fk_value}).find()

                    nested_instance.encapsulate_nested(depth=depth - 1)
                    setattr(self, nested_attr, nested_instance)

            # @nested_list support begins
            nested_lists = ReflectionUtils.get_nested_list_metadata(self.__class__)
            if nested_lists:
                for attr_name, info in nested_lists.items():
                    target_cls = resolve_class_by_name(info['class'])
                    foreign_key = info['foreign_key']

                    if target_cls:
                        related_items = target_cls(**{foreign_key: self.id}).find_all()

                        # Substitui qualquer método ou atributo existente com o mesmo nome
                        object.__setattr__(self, attr_name, related_items)  
            # @nested_list support ends

        if getattr(self, "clean_nested_keys", False):
            self.cleanup_foreign_keys()

        return self
    
    def list(self):
        """
        Retrieves all records of the domain entity from the database table,
        without applying any filters.

        This is equivalent to calling `find_all()` without setting any attributes.

        Returns:
            list: A list of domain instances, optionally with nested encapsulation.
        """
        return self.__class__().find_all()

    @validate # load_nested: bool = True
    def find(self: T) -> T:
        """
        Attempts to retrieve a single domain object from the data source 
        that matches the current object's DTO representation.

        This method instantiates a DAO (Data Access Object) based on the `self.dao` 
        blueprint and uses it to call `find_one`, passing the current object 
        converted to a DTO (via `as_dto()`).

        After synchronizing fields from the DTO into the current instance,
        it automatically applies nested encapsulation based on declared foreign keys.

        Returns:
            self: The current domain instance, fully hydrated, including nested domain objects.
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)
        obj = self.__dao__.find_one(dto=self.as_dto())
        if obj:
            self.sync(obj)
            self.normalize_foreign_keys()
            # Patch: load_nested.
            #if load_nested:
            self.encapsulate_nested()
            #/Patch: load_nested.    
        return self
    
    @validate
    def find_all(self: T) -> List[T]:
        
        """
        Retrieves all domain objects from the data source that match the 
        criteria defined by the current object's DTO representation.

        This method instantiates a DAO based on the `self.dao` blueprint and 
        invokes `find_all`, passing in the DTO version of the current object.

        Unlike `find`, which retrieves a single match, this method returns 
        a collection of matching results (e.g., a list of domain instances).

        Returns:
            A list or iterable of domain objects matching the provided criteria.

        Useful for querying multiple records based on partial or complete DTO data.
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)
        dto_list = self.__dao__.find_all(dto=self.as_dto())
        domains = self.encapsulate(dto_list=dto_list)

        for d in domains:
            if hasattr(d, "normalize_foreign_keys"):
                d.normalize_foreign_keys()
            d.encapsulate_nested()
        return domains
    
    # Joint_Find Methods:
    def call_dao_method(self, method_name: str, **params):
        """
        Calls a custom method on the DAO with the given parameters,
        and encapsulates the result if DTOs are returned.

        Args:
            method_name (str): The name of the DAO method to invoke.
            **params: Parameters to pass to the DAO method.

        Returns:
            list[Domain] | Domain | any: Encapsulated domain objects if DTOs are returned,
            otherwise returns raw results (e.g., bool, str).
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)

        dao_method = getattr(self.__dao__, method_name, None)
        if not callable(dao_method):
            raise AttributeError(f"Method '{method_name}' not found in DAO.")

        result = dao_method(**params)

        if result is None:
            return None

        if isinstance(result, list):
            if not result:
                return []
            if hasattr(result[0], 'sync'):
                domains = self.encapsulate(dto_list=result)
                for d in domains:
                    if hasattr(d, "normalize_foreign_keys"):
                        d.normalize_foreign_keys()
                    d.encapsulate_nested()
                return domains
            return result  # list of primitives

        if hasattr(result, 'sync'):
            domain = self.encapsulate(dto_list=[result])[0]
            if hasattr(domain, "normalize_foreign_keys"):
                domain.normalize_foreign_keys()
            domain.encapsulate_nested()
            return domain

        return result  # primitive
    
    def joint_find(self, query: str, **params):
        """
        Executes a custom join query using the DAO layer and processes the result appropriately.

        Behavior:
        - If the result is a list of DTOs, encapsulates them as domain objects.
        - If the result is a single DTO, encapsulates and returns it.
        - If the result is a list of primitives (str, bool, int...), returns as-is.
        - If the result is a single primitive value, returns as-is.

        Args:
            query (str): SQL query with <param> placeholders.
            **params: Named parameters used in the query.

        Returns:
            list[Domain] | Domain | any: Encapsulated domain objects or primitive results.
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)
        dto_model = self.__dao__.model
        result = self.__dao__.joint_find(query=query, dto_model=dto_model, **params)

        if result is None:
            return None

        if isinstance(result, list):
            if not result:
                return []
            if hasattr(result[0], 'sync'):
                domains = self.encapsulate(dto_list=result)
                for d in domains:
                    if hasattr(d, "normalize_foreign_keys"):
                        d.normalize_foreign_keys()
                    d.encapsulate_nested()
                return domains
            return result  # list of primitives

        if hasattr(result, 'sync'):
            domain = self.encapsulate(dto_list=[result])[0]
            if hasattr(domain, "normalize_foreign_keys"):
                domain.normalize_foreign_keys()
            domain.encapsulate_nested()
            return domain

        return result  # primitive

    #/Joint_find methods.
    
    @classmethod
    def encapsulate(cls, dto_list):
        """
        Converts a list of DTO objects into a list of domain objects 
        of the calling class (cls), including optional nested encapsulation.

        If the domain class defines 'foreign_keys', nested domain objects 
        will be instantiated automatically.

        Args:
            dto_list (list): List of DTOs (dict or objects with attributes).

        Returns:
            list: List of domain objects (instances of cls), fully hydrated.
        """
        result = []
        for dto in dto_list:
            domain_obj = ReflectionUtils.new_instance(blueprint=cls.model())
            domain_obj.sync(dto)

            # Normalize *_id fields and main id if necessary
            if hasattr(domain_obj, "normalize_foreign_keys"):
                domain_obj.normalize_foreign_keys()

            if hasattr(cls, 'foreign_keys'):
                domain_obj.encapsulate_nested() # For Nested Objects.
            result.append(domain_obj)
        return result
    
    @validate
    def update(self: T) -> T:
        """
        Updates the current domain object in the database.

        This method converts the domain object into its DTO representation,
        invokes the DAO update operation, and finally returns the updated object
        reloaded from the database.

        If the update fails, a custom UpdateOperationError will be raised.

        Returns:
            The updated domain object if successful.

        Raises:
            UpdateOperationError: If update fails or no object could be reloaded.
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)

        # Minimal safety: ensure ID is set
        try:
            updated = self.__dao__.update(dto=self.as_dto())
            if not updated:
                raise UpdateOperationError(dto=self.as_dto())

            # Return refreshed object from DB
            # obj = self.__dao__.find_one(dto=self.as_dto())
            # Return refreshed object from DB (reload by primary key only)
            reload_dto = self.as_dto().__class__(id=self.id)
            obj = self.__dao__.find_one(dto=reload_dto, raise_if_not_found=True)

            # Sync and encapsulate into current instance
            self.sync(obj)
            self.normalize_foreign_keys()
            self.encapsulate_nested()

            # Clean *_id if instructed by class
            if getattr(self, 'clean_nested_keys', False) and hasattr(self, 'foreign_keys'):
                for fk_field in self.foreign_keys.keys():
                    if hasattr(self, fk_field):
                        delattr(self, fk_field)

            return self

        except Exception as e:
            # Optional: log the error before raising
            log(f"Update failed: {e}")
            raise UpdateOperationError(dto=self.as_dto(), message=str(e))

    @validate
    def save(self: T, allow_duplicates: bool = False) -> T:
        """
        Inserts the current domain object into the database.

        This method controls duplicate inserts based on the assigned DTO fields.
        If `allow_duplicates` is set to False (default behavior), the ORM first checks
        whether a matching record already exists in the database using the DAO's `exists()` 
        method. If such a record is found, no insert is performed and the existing ID remains.

        If `allow_duplicates` is set to True, the ORM skips existence validation and always 
        attempts to insert the record. The database will assign a new unique ID via its primary key.

        This mechanism allows safe insertions where the business logic tolerates logically 
        duplicate rows.

        Args:
            allow_duplicates (bool, optional): 
                - If True: Always insert, allowing multiple identical rows (with different IDs).
                - If False (default): Prevents insertion if a similar record already exists.

        Returns:
            Domain: The domain object itself (hydrated with the generated or existing ID).

        Example:
            >>> schedule = Schedule(employee_id=1, date='2025-06-12', start_time='08:00', end_time='16:00')
            >>> result = schedule.save(allow_duplicates=False)
            >>> print(result.id)
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)
        dto = self.as_dto()

        try:
            if allow_duplicates or not self.__dao__.exists(dto=dto):
                self.__dao__.save(dto=dto)

            # 🔧 Patch: Sync the ID (and other attributes).
            self.sync(dto)
            self.normalize_foreign_keys()
            self.encapsulate_nested() 

            return self
        except Exception:
            raise SaveOperationError(dto=self.as_dto())

    @validate
    def persist(self: T, allow_duplicates: bool = False) -> T:
        """
        Persists the current domain object to the database.

        This method intelligently chooses between INSERT and UPDATE:

        - If the object has an assigned 'id', it performs UPDATE.
        - If no 'id' is assigned:
            - If allow_duplicates is False, checks if a matching record exists using find_one().
                - If found: updates it using its existing ID.
                - If not found: inserts a new record.
            - If allow_duplicates is True, skips the check and inserts directly.

        Returns:
            Domain: The domain object itself, updated with ID and database state.

        Raises:
            SaveOperationError: If the insert operation fails.
            UpdateOperationError: If the update operation fails.
        """
        self.__dao__ = ReflectionUtils.new_instance(blueprint=self.dao)
        dto = self.as_dto()

        try:
            if dto.id:
                try:
                    self.__dao__.update(dto)
                except Exception:
                    raise UpdateOperationError(dto=dto)

            elif not allow_duplicates:
                try:
                    existing = self.__dao__.find_one(dto)
                except Exception:
                    raise SaveOperationError(dto=dto)

                if existing:
                    dto.id = existing.id
                    try:
                        self.__dao__.update(dto)
                    except Exception:
                        raise UpdateOperationError(dto=dto)
                else:
                    try:
                        self.__dao__.save(dto)
                    except Exception:
                        raise SaveOperationError(dto=dto)

            else:
                try:
                    self.__dao__.save(dto)
                except Exception:
                    raise SaveOperationError(dto=dto)

            self.sync(dto)
            self.normalize_foreign_keys()
            return self

        except (SaveOperationError, UpdateOperationError):
            raise
        except Exception:
            raise SaveOperationError(dto=self.as_dto())

    def delete(self) -> bool:
        """
        Deletes the current domain object from the database using its DAO.

        Returns
        -------
        bool
            True if deletion was successful.

        Raises
        ------
        ValueError
            If the domain object has no 'id' set.
        """
        if not self.id:
            raise ValueError(f"Cannot delete {self.__class__.__name__}: 'id' is missing.")

        dto = self.as_dto()
        return self.get_dao().delete(dto)

    def sync(self, obj, ignore_private=False):
        """
        Synchronizes the Domain object from a DTO, dictionary, or another domain instance.

        This method performs a shallow synchronization: it copies all available attributes from 
        the provided object into the current Domain instance, including foreign key fields if present.

        IMPORTANT:
            - No foreign key filtering is performed at this stage.
            - Cleanup of foreign keys (removal of *_id fields after nested encapsulation) 
            must be handled separately via `cleanup_foreign_keys()`, if desired.
            - This design allows the sync logic to remain generic, flexible, and compatible 
            across both flat and nested object structures.

        Args:
            obj (object or dict): The source object or dictionary to synchronize from.
            ignore_private (bool, optional): Whether to ignore private fields (those starting with '_').
                Defaults to False.

        Returns:
            self: The synchronized Domain instance (fluent interface).
        
        Example:
            >>> dto = ContractDto(id=1, member_id=2, company_id=3)
            >>> domain = Enrolment().sync(dto)
            >>> print(domain.member_id)
            2
        """
        if isinstance(obj, dict):
            data = obj.copy()
        else:
            data = vars(obj).copy()

        super().sync(data, ignore_private=ignore_private)
        return self
    
    def cleanup_foreign_keys(self):
        """
        Removes foreign key fields from the domain object after encapsulation,
        based on the foreign_keys mapping.

        This allows keeping only the nested domain objects and discarding the *_id fields.

        This method is safe to call multiple times.

        Example:
            If self.foreign_keys = {'member_id': Member}, this will remove 'member_id' attribute.
        """
        if not hasattr(self.__class__, 'foreign_keys'):
            return

        for fk_field in self.__class__.foreign_keys.keys():
            if hasattr(self, fk_field):
                delattr(self, fk_field)
    
    def normalize_foreign_keys(self):
        """
        Recursively converts any *_id string attributes and main `id` field to UUID objects (if valid),
        and applies the same normalization to any nested foreign key domain objects.
        """
        import uuid
        from miniorm.uuid_utils import is_valid_uuid

        # Convert self.id if needed
        if hasattr(self, "id") and isinstance(self.id, str) and is_valid_uuid(self.id):
            self.id = uuid.UUID(self.id)

        # Patch for tuple-based foreign_keys support
        fk_mappings = {}
        for fk_field, mapping in getattr(self, 'foreign_keys', {}).items():
            if isinstance(mapping, tuple):
                attr_name = mapping[0]
            else:
                attr_name = fk_field.replace('_id', '')
            fk_mappings[attr_name] = fk_field
        # /Patch

        for attr_name, value in vars(self).items():
            # Patch for foreign key normalization using tuple-aware mapping
            fk_field = fk_mappings.get(attr_name, attr_name)
            if fk_field.endswith('_id') and isinstance(value, str) and is_valid_uuid(value):
                setattr(self, fk_field, uuid.UUID(value))
            elif isinstance(value, Domain):
                value.normalize_foreign_keys()
            # /Patch

        return self  # Allow method chaining

    def __str__(self):
        """
        Returns a pretty-printed JSON string representation of the object,
        including nested objects, while ignoring specific attributes that
        are not relevant for serialization.

        The method uses `ReflectionUtils.obj_to_dict` to recursively convert 
        the object and its nested attributes into a dictionary. Certain fields 
        such as 'table', 'dao', '__dao__', 'dto', and '__dto__' are excluded 
        from the output to avoid serializing unnecessary or redundant data 
        (e.g., database access objects or metadata).

        This customized string representation is useful for debugging, 
        logging, or displaying the internal state of the object in a 
        human-readable JSON format.
        """
        def default_serializer(o):
            if isinstance(o, uuid.UUID):
                return str(o)
            return str(o)

        return json.dumps(ReflectionUtils.obj_to_dict(
            self, 
            ignore=['table', 'dao', '__dao__', 'dto', '__dto__'],
            clean_nested_keys=getattr(self, "clean_nested_keys", False)
        ), indent=4, default=default_serializer)
  
    def __repr__(self):
        """
        Returns a friendly and compact string representation of the domain object for debugging and logging purposes.

        Instead of showing only the memory address (default Python behavior), this customized __repr__ includes 
        key identifying attributes to make inspection easier during debugging or console usage.

        Behavior:
            - Displays the class name.
            - Includes key fields when available: 'id', 'username', 'name'.
            - Fields that are None are automatically skipped to avoid noise.
            - Falls back to class name only if none of the key fields are present.

        This representation helps quickly identify which specific object instance you're working with 
        in complex nested structures or ORM operations.

        Example:
            >>> member = Member(id=1, username="ericxlive")
            >>> print(repr(member))
            <Member(id=1, username=ericxlive)>

            >>> company = Company(id=10, name="Zentek")
            >>> print(repr(company))
            <Company(id=10, name=Zentek)>

        Returns:
            str: A compact string summarizing the object's class and key fields.
        """
        summary_fields = []
        for key in ['id', 'username', 'name']:
            value = getattr(self, key, None)
            if value is not None:
                summary_fields.append(f"{key}={value}")
        summary_str = ", ".join(summary_fields)
        return f"<{self.__class__.__name__}({summary_str})>"