from datetime import datetime, date, time

def print_color(text, color="RED"):
    colors = {
        "RED": "\033[91m",
        "PURPLE": "\033[95m",
        "CYAN": "\033[96m",
        "ENDC": "\033[00m"
    }
    color_code = colors.get(color.upper(), colors["RED"])
    print(f"{color_code}{text}{colors['ENDC']}")

def query_format(text):
    return " ".join(text.split()).strip()

def log(query: str, params: dict = None, color: str = "RED"):
    if params:
        for key, value in params.items():
            if isinstance(value, str):
                value = f"'{value}'"
            elif isinstance(value, (datetime, date)):
                value = f"'{value.strftime('%Y-%m-%d')}'"
            elif isinstance(value, time):
                value = f"'{value.strftime('%H:%M:%S')}'"
            elif value is None:
                value = "NULL"
            query = query.replace(f"%({key})s", str(value))
    
    formatted = query_format(query)
    print_color(formatted, color)
    print("")  # Linha em branco para espaçamento visual