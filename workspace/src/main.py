def greet(name):
    """
    Returns a greeting message based on the provided name.

    Parameters:
    name (str or None): The name of the person to greet. If None, greets as a guest.

    Returns:
    str: A greeting message.
    """
    if name is None:
        return "Hello, Guest!"
    elif name == '':
        return "Hello, Stranger!"
    elif isinstance(name, (bytes, type(object()))):
        return "Hello, Guest!"
    return f'Hello, {name}!'