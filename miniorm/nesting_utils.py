def nested_list(domain_class: str, foreign_key: str):
    """
    Marks a method or property as a nested list to be loaded via encapsulation.

    Parameters
    ----------
    domain_class : str
        The name of the domain class that represents the nested entity.
    foreign_key : str
        The foreign key in the nested entity that refers back to the parent.
    """
    def decorator(func):
        func._nested_list = {
            "target": domain_class,
            "foreign_key": foreign_key
        }
        return func
    return decorator