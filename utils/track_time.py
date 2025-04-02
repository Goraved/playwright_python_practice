import inspect
import logging
import re
import time
from functools import wraps
from typing import Optional

import pytest

TO_EXCLUDE = ['catch_response', 'wait_for_loader', 'wait_for_page_load', 'open', 'click', 'fill', 'wait_until_hidden',
              'wait_until_visible', 'wait_until_enabled', 'wait_until_disabled', 'wait_for_ended_process']


def track_execution_time(func):
    """
    Decorator to measure the execution time of methods and fixtures
    and log the details (name and time) in pytest-html.

    Functions in the to_exclude list are only logged if their execution time exceeds 5 seconds.
    All other functions are logged regardless of execution time.

    Args:
        func (callable): The function or fixture to wrap.

    Returns:
        callable: The wrapped function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get current test item
        item = getattr(pytest, 'current_item', None)
        if not item:
            return func(*args, **kwargs)

        # Initialize execution log and call stack if not exists
        if not hasattr(item, 'execution_log'):
            item.execution_log = []
        if not hasattr(item, 'call_stack'):
            item.call_stack = []

        start_time = time.perf_counter()

        # Determine the name to log
        function_name = func.__name__
        func_type = 'function'
        stack: Optional[list[inspect.FrameInfo]] = None
        result = None

        if function_name == "factory":
            # Inspect the call stack to find the context of the call
            stack = inspect.stack()
            for frame in stack:
                if (frame.function.startswith("factory") or frame.function.startswith(
                        'test_') or frame.function.startswith('create_')) and frame.code_context:
                    # Extract the line of code where factory is called
                    line_of_code = frame.code_context[0].strip()
                    # Enhanced regex to match both assignment and direct calls
                    match = re.search(r"(?:\w+\s*=\s*)?(\w+)\(", line_of_code)
                    if match:
                        function_name = match.group(1)  # Get the caller name
                        func_type = 'fixture'
                        break
        else:
            path = inspect.stack()[1].filename
            func_type = 'fixture' if 'fixture' in path or 'conftest' in path else 'function'

        # Add current function to call stack
        current_call = {'name': function_name, 'type': func_type, 'level': len(item.call_stack),
                        'start_time': start_time}
        item.call_stack.append(current_call)

        # Execute the function
        try:
            result = func(*args, **kwargs)
        finally:
            # Calculate execution time
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Create log entry with proper indentation showing hierarchy
            indent = '  ' * current_call['level']
            log_entry = f"{indent}{func_type} - {function_name}: {execution_time:.4f} seconds"

            # Only log if function is not in to_exclude list or if execution time > 5 seconds

            should_log = function_name not in TO_EXCLUDE or execution_time > 5

            if should_log:
                if function_name == "factory":
                    print(f'Wrong time tracking name - {[s.function for s in stack]}')
                elif function_name in TO_EXCLUDE and args:
                    # Try to get selector from first arg if it's a Playwright Locator
                    try:
                        from playwright.sync_api import Locator
                        if hasattr(args[0], 'raw') and isinstance(args[0].raw, Locator):
                            # Use str() to get the string representation which contains the selector
                            selector_info = str(args[0].raw)
                            log_entry = f"{indent}{func_type} - {function_name}({selector_info}): {execution_time:.4f} seconds"
                    except (ImportError, TypeError, AttributeError):
                        pass
                # Add a warning log if function took more than 10 seconds
                if execution_time > 10:
                    logging.warning(f"{function_name} took over 10 seconds to execute: {execution_time:.4f} seconds")
                item.execution_log.insert(0, (start_time, log_entry))

            # Remove current function from call stack
            item.call_stack.pop()

        return result

    return wrapper
