import json

def print_as_json(objects: list):
    """
    Pretty prints a list of domain objects as JSON, assuming each object 
    implements __str__ to return a valid JSON string.
    
    Parameters:
        objects (list): List of domain objects (e.g., instances of Domain subclasses)
    """
    print(json.dumps([json.loads(str(obj)) for obj in objects], indent=4))