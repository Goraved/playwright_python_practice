class SoftAssertContextManager:
    """
    A context manager for soft assertions in tests.
    Collects assertion failures and allows tests to continue running.
    """

    def __init__(self):
        self.failures = []

    def __enter__(self):
        """
        Start the soft assertion context.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Capture exceptions (assertion failures) and store them.
        """
        if exc_type is AssertionError:
            self.failures.append(f'{len(self.failures) + 1}. Line: {traceback.tb_lineno}. \n{exc_value} ')
            return True  # Suppress the exception

    def has_failures(self):
        """
        Check if there are any failures recorded.
        """
        return bool(self.failures)

    def get_failures(self):
        """
        Retrieve all recorded failures.
        """
        return self.failures
