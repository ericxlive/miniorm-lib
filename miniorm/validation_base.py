import functools

class ValidationObserver:
    """
    ValidationObserver: Cross-cutting validation mechanism for Domain-level operation constraints.

    Supports validation logic for methods like save, update, find, etc., defined via
    a `restrictions` dict inside Domain classes.

    Restrictions can define:
        - required: list of fields that must be present
        - required_any: at least one field from a list
        - mutually_exclusive: groups of fields where only one may be set

    Example:
        restrictions = {
            'save': {
                'required': ['name', 'company_id'],
                'required_any': ['work_group', 'department'],
                'mutually_exclusive': [['work_group', 'department']]
            }
        }
    """

    class ValidationError(Exception):
        def __init__(self, domain, operation, missing_fields):
            self.domain = domain
            self.operation = operation
            self.missing_fields = missing_fields
            message = f"Validation failed for operation '{operation}' on {domain.__class__.__name__}: missing or invalid fields {missing_fields}"
            super().__init__(message)

    @staticmethod
    def validate(domain, operation: str):
        restrictions = getattr(domain.__class__, 'restrictions', {})
        rule = restrictions.get(operation)
        if not rule:
            return

        missing = []

        # Required fields
        for field in rule.get('required', []):
            if getattr(domain, field, None) is None:
                missing.append(field)

        # Required any (at least one must be present)
        required_any = rule.get('required_any', [])
        if required_any:
            if not any(getattr(domain, f, None) is not None for f in required_any):
                missing.append(f"[any of: {', '.join(required_any)}]")

        # Mutually exclusive (only one should be present)
        for group in rule.get('mutually_exclusive', []):
            filled = [f for f in group if getattr(domain, f, None) is not None]
            if len(filled) > 1:
                raise ValidationObserver.ValidationError(
                    domain,
                    operation,
                    [f"[mutually exclusive violation: {', '.join(group)}]"]
                )

        if missing:
            raise ValidationObserver.ValidationError(domain, operation, missing)


def validate(func):
    """
    Decorator that applies ValidationObserver based on method name and class-level `restrictions`.

    Example:
        class MyDomain(Domain):
            restrictions = {
                'save': {
                    'required': ['name'],
                    'required_any': ['email', 'phone'],
                    'mutually_exclusive': [['email', 'phone']]
                }
            }

            @validate
            def save(self):
                return super().save()

    Returns:
        Callable: Wrapped function with pre-validation.
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        operation = func.__name__
        ValidationObserver.validate(self, operation)
        return func(self, *args, **kwargs)
    return wrapper


def validate_args_being_fixed(*, required=None, required_any=None, mutually_exclusive=None):
    """
    Decorator to validate only the passed arguments of a method.

    Usage:
        @validate_args(required=['user_id'], mutually_exclusive=[['email', 'phone']])
        def do_something(self, user_id=None, email=None, phone=None):
            ...

    Rules:
        - required: fields that must be passed and non-None
        - required_any: at least one must be passed and non-None
        - mutually_exclusive: if more than one in group is passed, raise error

    Returns:
        Callable: Function with argument-level validation
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            from inspect import signature
            bound = signature(func).bind(self, *args, **kwargs)
            bound.apply_defaults()
            all_args = bound.arguments

            missing = []

            # Required
            for field in required or []:
                if all_args.get(field) is None:
                    missing.append(field)

            # Required any
            if required_any:
                if not any(all_args.get(f) is not None for f in required_any):
                    missing.append(f"[any of: {', '.join(required_any)}]")

            # Mutually exclusive
            for group in mutually_exclusive or []:
                filled = [f for f in group if all_args.get(f) is not None]
                if len(filled) > 1:
                    raise ValidationObserver.ValidationError(
                        self,
                        func.__name__,
                        [f"[mutually exclusive violation: {', '.join(group)}]"]
                    )

            if missing:
                raise ValidationObserver.ValidationError(self, func.__name__, missing)

            return func(self, *args, **kwargs)
        return wrapper
    return decorator

def validate_args(*, required=None, required_any=None, mutually_exclusive=None):
    """
    Decorator to validate only explicitly passed arguments of a method.

    This version avoids accessing the actual values to prevent triggering side effects
    on complex objects (e.g., Domain instances). It only checks for presence in kwargs.

    Returns:
        Callable: Function with argument-level validation
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            passed = set(kwargs.keys())

            missing = []

            # Required fields: must be explicitly passed and not None
            for field in required or []:
                if field not in passed or kwargs[field] is None:
                    missing.append(field)

            # Required any: at least one must be passed and not None
            if required_any:
                if not any(f in passed and kwargs[f] is not None for f in required_any):
                    missing.append(f"[any of: {', '.join(required_any)}]")

            # Mutually exclusive: only one field in each group may be passed and not None
            for group in mutually_exclusive or []:
                filled = [f for f in group if f in passed and kwargs[f] is not None]
                if len(filled) > 1:
                    raise ValidationObserver.ValidationError(
                        self,
                        func.__name__,
                        [f"[mutually exclusive violation: {', '.join(group)}]"]
                    )

            if missing:
                raise ValidationObserver.ValidationError(self, func.__name__, missing)

            return func(self, *args, **kwargs)
        return wrapper
    return decorator

import functools

def validate_attributes(*, required=None, required_any=None, mutually_exclusive=None):
    """
    Decorator to validate object-level attributes (not method arguments).

    - `required`: attributes that must exist and not be None
    - `required_any`: at least one of the listed attributes must be non-None
    - `mutually_exclusive`: only one attribute in each group may be set

    Example usage:
        @validate_attributes(required=['name'], mutually_exclusive=[['company_id', 'work_group_id']])
        def save(self):
            ...

    Raises:
        ValidationObserver.ValidationError if validation fails.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            from miniorm.validation_base import ValidationObserver  # Import here to avoid circular dependency
            missing = []

            # Required
            for attr in required or []:
                if not hasattr(self, attr) or getattr(self, attr) is None:
                    missing.append(attr)

            # Required any
            if required_any:
                if not any(
                    hasattr(self, attr) and getattr(self, attr) is not None
                    for attr in required_any
                ):
                    missing.append(f"[any of: {', '.join(required_any)}]")

            # Mutually exclusive
            for group in mutually_exclusive or []:
                filled = [
                    attr for attr in group
                    if hasattr(self, attr) and getattr(self, attr) is not None
                ]
                if len(filled) > 1:
                    raise ValidationObserver.ValidationError(
                        self,
                        func.__name__,
                        [f"[mutually exclusive violation: {', '.join(group)}]"]
                    )

            if missing:
                raise ValidationObserver.ValidationError(self, func.__name__, missing)

            return func(self, *args, **kwargs)
        return wrapper
    return decorator