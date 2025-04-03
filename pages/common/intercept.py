import json
from contextlib import contextmanager
from typing import Optional


class RequestResponseModifier:
    def __init__(self, page):
        self.page = page

    @contextmanager
    def modify_request_body(self, url_to_modify: str, param_to_update: str, new_value: Optional[str]):
        """
        Context manager to intercept and modify the JSON body of a request matching a specified URL.

        Args:
            url_to_modify (str): URL substring or pattern to identify the request to intercept.
            param_to_update (str): The JSON key to update in the request body.
            new_value (str): The new value for the specified JSON key. If None, the key is removed.
        """

        def handle_route(route):
            # Check if the request URL contains the specified substring
            if url_to_modify in route.request.url:
                try:
                    # Parse the JSON body of the request
                    body = route.request.post_data_json['data']
                    # Check if the parameter to update is in the JSON body
                    if param_to_update in body:
                        # If new_value is None, remove the parameter from the JSON body
                        if new_value is None:
                            del body[param_to_update]
                        # Otherwise, update the parameter with new_value
                        else:
                            body[param_to_update] = new_value
                        # Convert the modified JSON body back to a string
                        modified_body = json.dumps({'data': body})
                        # Continue the request with the modified JSON body
                        route.continue_(post_data=modified_body)
                    else:
                        # If the parameter is not in the JSON body, continue the request without modification
                        route.continue_()
                except Exception as e:
                    # Print an error message if an exception occurs
                    print(f"Error modifying request body: {e}")
                    # Continue the request without modification
                    route.continue_()
            else:
                # If the request URL does not contain the specified substring, continue the request without modification
                route.continue_()

        # Setup route interception
        self.page.route("**/*", handle_route)
        try:
            yield
        finally:
            # Automatically stop intercepting when context is exited
            self.page.unroute("**/*", handle_route)

    @contextmanager
    def modify_response_body(self, url_to_modify: str, param_to_update: str, new_value: Optional[str]):
        """
        Context manager to intercept and modify the JSON body of a response matching a specified URL.

        Args:
            url_to_modify (str): URL substring or pattern to identify the response to intercept.
            param_to_update (str): The JSON key to update in the response body.
            new_value (str): The new value for the specified JSON key. If None, the key is removed.
        """

        def handle_route(route):
            # Check if the request URL contains the specified substring
            if url_to_modify in route.request.url:
                # Fetch the response for the intercepted request
                response = route.fetch()
                try:
                    # Parse the JSON body of the response
                    body = response.json()
                    # Check if the parameter to update is in the JSON body
                    if param_to_update in body:
                        # If new_value is None, remove the parameter from the JSON body
                        if new_value is None:
                            del body[param_to_update]
                        # Otherwise, update the parameter with new_value
                        else:
                            body[param_to_update] = new_value
                        # Convert the modified JSON body back to a string
                        modified_body = json.dumps(body)
                        # Fulfill the request with the modified JSON body
                        route.fulfill(
                            status=response.status,
                            headers=response.headers,
                            body=modified_body
                        )
                    else:
                        # If the parameter is not in the JSON body, fulfill the request without modification
                        route.fulfill(
                            status=response.status,
                            headers=response.headers,
                            body=json.dumps(body)
                        )
                except Exception as e:
                    # Print an error message if an exception occurs
                    print(f"Error modifying response body: {e}")
                    # Fulfill the request without modification
                    route.fulfill(
                        status=response.status,
                        headers=response.headers,
                        body=response.body()
                    )
            else:
                # If the request URL does not contain the specified substring, continue the request without modification
                route.continue_()

        # Setup route interception
        self.page.route("**/*", handle_route)
        try:
            yield
        finally:
            # Automatically stop intercepting when context is exited
            self.page.unroute("**/*", handle_route)

    @contextmanager
    def modify_url(self, url_pattern: str, param_to_replace: str, new_value: str):
        """
        Context manager to intercept and modify a specific part of URLs matching a pattern.

        Args:
            url_pattern (str): URL substring or pattern to identify the requests to intercept.
            param_to_replace (str): The URL parameter or path segment to replace.
            new_value (str): The new value to substitute for the specified URL parameter or path segment.
        """

        def handle_route(route):
            if url_pattern in route.request.url:
                modified_url = route.request.url.replace(param_to_replace, new_value)
                route.continue_(url=modified_url)
            else:
                route.continue_()

        # Setup route interception
        self.page.route("**/*", handle_route)
        try:
            yield
        finally:
            # Automatically stop intercepting when context is exited
            self.page.unroute("**/*", handle_route)
