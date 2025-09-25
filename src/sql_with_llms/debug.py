import ast
import os

import litellm


def set_debug(on: bool | None = None):
    """Helper function to turn debug based on an argument"""
    if on is None:
        try:
            debug = ast.literal_eval(os.getenv("DEBUG", "0"))
        except ValueError:
            debug = False
    else:
        debug = on
    if debug:
        litellm._turn_on_debug()
    else:
        litellm.suppress_debug_info = True
