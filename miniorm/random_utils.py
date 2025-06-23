import secrets, string

def random_hash():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(20))