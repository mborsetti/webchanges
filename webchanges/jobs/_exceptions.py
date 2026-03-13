"""Job exceptions."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

from http.client import responses as http_response_names
from typing import Any


class NotModifiedError(Exception):
    """Raised when an HTTP 304 response status code (Not Modified client redirection) is received or the strong
    validation ETag matches the previous one; this indicates that there was no change in content.
    """


class TransientHTTPError(Exception):
    """Raised by subclasses of UrlJobBase when one of these HTTP response status codes is received:

    - 429 Too Many Requests
    - 500 Internal Server Error
    - 502 Bad Gateway
    - 503 Service Unavailable
    - 504 Gateway Timeout
    """

    status_code: int

    def __init__(self, *args: object, status_code: int) -> None:
        super().__init__(*args)
        self.status_code = status_code


class TransientBrowserError(Exception):
    """Raised by BrowserJob when a transient error is returned by the browser, either as a PlaywrightTimeoutError or
    as a browser error listed in the 100-199 Connection related errors.

    The args[0] will contain the string 'PlaywrightTimeoutError' or the text of the browser error.
    """

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class BrowserResponseError(Exception):
    """Raised by 'url' jobs with 'use_browser: true' (i.e. using Playwright) when an HTTP error response status code is
    received and is not one of the other Exceptions.
    """

    def __init__(self, args: tuple[Any, ...], status_code: int | None = None) -> None:
        """:param args: Tuple with the underlying error args, typically a string with the error text.
        :param status_code: The HTTP status code received.
        """
        Exception.__init__(self, *args)
        self.status_code = status_code

    def __str__(self) -> str:
        if self.status_code:
            return (
                f'{self.__class__.__name__}: Received response HTTP {self.status_code} '
                f'{http_response_names.get(self.status_code, "")}'
                + (f' with content "{self.args[0]}"' if self.args[0] else '')
            )
        return str(self.args[0])
