"""BrowserJob — retrieve a URL using a real web browser."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import html
import json
import logging
import os
import platform
import re
import tempfile
import time
import warnings
from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal
from urllib.parse import SplitResult, SplitResultBytes, parse_qsl, quote, urlencode, urlparse, urlsplit

from webchanges import __project_name__
from webchanges.jobs._base import UrlJobBase
from webchanges.jobs._exceptions import (
    BrowserResponseError,
    NotModifiedError,
    TransientBrowserError,
    TransientHTTPError,
)

# https://stackoverflow.com/questions/39740632
if TYPE_CHECKING:
    try:
        from playwright.sync_api import Page, Response
    except ImportError:  # pragma: no cover
        pass

    from webchanges.handler import JobState

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # ty:ignore[invalid-assignment]

logger = logging.getLogger(__name__)


class BrowserJob(UrlJobBase):
    """Retrieve a URL using a real web browser (use_browser: true)."""

    __kind__ = 'browser'
    __is_browser__ = True

    __required__: tuple[str, ...] = ('use_browser',)
    __optional__: tuple[str, ...] = (
        'block_elements',
        'evaluate',
        'http_credentials',
        'ignore_default_args',
        'ignore_https_errors',
        'init_script',
        'initialization_js',
        'initialization_url',
        'navigate',  # deprecated
        'referer',
        'switches',
        'user_data_dir',
        'wait_for',  # deprecated (pyppeteer backwards compatibility)
        'wait_for_function',
        'wait_for_navigation',  # deprecated (pyppeteer backwards compatibility)
        'wait_for_selector',
        'wait_for_timeout',
        'wait_for_url',
        'wait_until',
    )

    use_browser = True
    _playwright: Any = None
    _playwright_browsers: dict = {}

    proxy_username: str = ''
    proxy_password: str = ''

    # See https://source.chromium.org/chromium/chromium/src/+/master:net/base/net_error_list.h
    chromium_connection_errors = (  # range 100-199 Connection related errors
        'net::ERR_CONNECTION_CLOSED',  # 100
        'net::ERR_CONNECTION_RESET',  # 101
        'net::ERR_CONNECTION_REFUSED',  # 102
        'net::ERR_CONNECTION_ABORTED',  # 103
        'net::ERR_CONNECTION_FAILED',  # 104
        'net::ERR_NAME_NOT_RESOLVED',  # 105
        'net::ERR_INTERNET_DISCONNECTED',  # 106
        'net::ERR_SSL_PROTOCOL_ERROR',  # 107
        'net::ERR_ADDRESS_INVALID',  # 108
        'net::ERR_ADDRESS_UNREACHABLE',  # 109
        'net::ERR_SSL_CLIENT_AUTH_CERT_NEEDED',  # 110
        'net::ERR_TUNNEL_CONNECTION_FAILED',  # 111
        'net::ERR_NO_SSL_VERSIONS_ENABLED',  # 112
        'net::ERR_SSL_VERSION_OR_CIPHER_MISMATCH',  # 113
        'net::ERR_SSL_RENEGOTIATION_REQUESTED',  # 114
        'net::ERR_PROXY_AUTH_UNSUPPORTED',  # 115
        'net::ERR_CERT_ERROR_IN_SSL_RENEGOTIATION',  # 116
        'net::ERR_BAD_SSL_CLIENT_AUTH_CERT',  # 117
        'net::ERR_CONNECTION_TIMED_OUT',  # 118
        'net::ERR_HOST_RESOLVER_QUEUE_TOO_LARGE',  # 119
        'net::ERR_SOCKS_CONNECTION_FAILED',  # 120
        'net::ERR_SOCKS_CONNECTION_HOST_UNREACHABLE',  # 121
        'net::ERR_ALPN_NEGOTIATION_FAILED',  # 122
        'net::ERR_SSL_NO_RENEGOTIATION',  # 123
        'net::ERR_WINSOCK_UNEXPECTED_WRITTEN_BYTES',  # 124
        'net::ERR_SSL_DECOMPRESSION_FAILURE_ALERT',  # 125
        'net::ERR_SSL_BAD_RECORD_MAC_ALERT',  # 126
        'net::ERR_PROXY_AUTH_REQUESTED',  # 127
        'net::ERR_PROXY_CONNECTION_FAILED',  # 130
        'net::ERR_MANDATORY_PROXY_CONFIGURATION_FAILED',  # 131
        'net::ERR_PRECONNECT_MAX_SOCKET_LIMIT',  # 133
        'net::ERR_SSL_CLIENT_AUTH_PRIVATE_KEY_ACCESS_DENIED',  # 134
        'net::ERR_SSL_CLIENT_AUTH_CERT_NO_PRIVATE_KEY',  # 135
        'net::ERR_PROXY_CERTIFICATE_INVALID',  # 136
        'net::ERR_NAME_RESOLUTION_FAILED',  # 137
        'net::ERR_NETWORK_ACCESS_DENIED',  # 138
        'net::ERR_TEMPORARILY_THROTTLED',  # 139
        'net::ERR_SSL_CLIENT_AUTH_SIGNATURE_FAILED',  # 141
        'net::ERR_MSG_TOO_BIG',  # 142
        'net::ERR_WS_PROTOCOL_ERROR',  # 145
        'net::ERR_ADDRESS_IN_USE',  # 147
        'net::ERR_SSL_PINNED_KEY_NOT_IN_CERT_CHAIN',  # 150
        'net::ERR_CLIENT_AUTH_CERT_TYPE_UNSUPPORTED',  # 151
        'net::ERR_SSL_DECRYPT_ERROR_ALERT',  # 153
        'net::ERR_WS_THROTTLE_QUEUE_TOO_LARGE',  # 154
        'net::ERR_SSL_SERVER_CERT_CHANGED',  # 156
        'net::ERR_SSL_UNRECOGNIZED_NAME_ALERT',  # 159
        'net::ERR_SOCKET_SET_RECEIVE_BUFFER_SIZE_ERROR',  # 160
        'net::ERR_SOCKET_SET_SEND_BUFFER_SIZE_ERROR',  # 161
        'net::ERR_SOCKET_RECEIVE_BUFFER_SIZE_UNCHANGEABLE',  # 162
        'net::ERR_SOCKET_SEND_BUFFER_SIZE_UNCHANGEABLE',  # 163
        'net::ERR_SSL_CLIENT_AUTH_CERT_BAD_FORMAT',  # 164
        'net::ERR_ICANN_NAME_COLLISION',  # 166
        'net::ERR_SSL_SERVER_CERT_BAD_FORMAT',  # 167
        'net::ERR_CT_STH_PARSING_FAILED',  # 168
        'net::ERR_CT_STH_INCOMPLETE',  # 169
        'net::ERR_UNABLE_TO_REUSE_CONNECTION_FOR_PROXY_AUTH',  # 170
        'net::ERR_CT_CONSISTENCY_PROOF_PARSING_FAILED',  # 171
        'net::ERR_SSL_OBSOLETE_CIPHER',  # 172
        'net::ERR_WS_UPGRADE',  # 173
        'net::ERR_READ_IF_READY_NOT_IMPLEMENTED',  # 174
        'net::ERR_NO_BUFFER_SPACE',  # 176
        'net::ERR_SSL_CLIENT_AUTH_NO_COMMON_ALGORITHMS',  # 177
        'net::ERR_EARLY_DATA_REJECTED',  # 178
        'net::ERR_WRONG_VERSION_ON_EARLY_DATA',  # 179
        'net::ERR_TLS13_DOWNGRADE_DETECTED',  # 180
        'net::ERR_SSL_KEY_USAGE_INCOMPATIBLE',  # 181
        'net::ERR_INVALID_ECH_CONFIG_LIST',  # 182
        'net::ERR_ECH_NOT_NEGOTIATED'  # 183
        'net::ERR_ECH_FALLBACK_CERTIFICATE_INVALID',  # 184
        'net::ERR_PROXY_UNABLE_TO_CONNECT_TO_DESTINATION'  # 186
        'net::ERR_PROXY_DELEGATE_CANCELED_CONNECT_REQUEST'  # 187
        'net::ERR_PROXY_DELEGATE_CANCELED_CONNECT_RESPONSE',  # 188
    )

    def get_location(self) -> str:
        """Get the 'location' of the job, i.e. the (user_visible) URL.

        :returns: The user_visible_url or URL of the job.
        """
        return self.user_visible_url or self.url

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location. Used for changing location (uuid)."""
        self.url = location
        self.guid = self.get_guid()

    @staticmethod
    def get_user_agent_platform() -> str:
        # Get system information
        system_name = platform.system()  # e.g., 'Windows', 'Linux', 'Darwin' (macOS)
        machine_arch = platform.machine()  # e.g., 'x86_64', 'AMD64'

        # Create a basic platform string
        if system_name == 'Windows':
            machine_arch = machine_arch.replace('AMD64', 'Win64; x64')
            nt_version = platform.version().rsplit('.', maxsplit=1)[0]
            platform_string = f'Windows NT {nt_version}; {machine_arch}'
        elif system_name == 'Linux':
            platform_string = f'X11; Linux {machine_arch}'
        elif system_name == 'Darwin':
            platform_string = f'Macintosh; Intel Mac OS X {platform.mac_ver()[0].replace(".", "_")}'
        else:
            platform_string = f'{system_name}; {machine_arch}'
        return platform_string

    def _save_error_files(
        self,
        page: Page,
    ) -> None:
        """Helper function to save screenshot and html content files after a Playwright Error"""
        from playwright.sync_api import Error as PlaywrightError

        screenshot_filename = tempfile.NamedTemporaryFile(
            prefix=f'{__project_name__}_screenshot_{self.index_number}_', suffix='.png', delete=False
        ).name
        try:
            page.screenshot(path=screenshot_filename)
            logger.info(f'Job {self.index_number}: Screenshot saved at {screenshot_filename}')
        except PlaywrightError:
            Path(screenshot_filename).unlink()
        full_filename = tempfile.NamedTemporaryFile(
            prefix=f'{__project_name__}_screenshot-full_{self.index_number}_',
            suffix='.png',
            delete=False,
        ).name
        try:
            page.screenshot(path=full_filename, full_page=True)
            logger.info(f'Job {self.index_number}: Full page image saved at {full_filename}')
        except PlaywrightError:
            Path(full_filename).unlink()
        html_filename = tempfile.NamedTemporaryFile(
            prefix=f'{__project_name__}_content_{self.index_number}_', suffix='.html', delete=False
        ).name
        try:
            Path(html_filename).write_text(page.content())
            logger.info(f'Job {self.index_number}: Page HTML content saved at {html_filename}')
        except PlaywrightError:
            Path(html_filename).unlink()

    def retrieve(  # noqa: C901 mccabe complexity too high
        self,
        job_state: JobState,
        headless: bool = True,
        response_handler: Callable[
            [Page, str, Literal['commit', 'domcontentloaded', 'load', 'networkidle'] | None, str | None], Response
        ]
        | None = None,
        content_handler: Callable[[Page], tuple[str | bytes, str, str]] | None = None,
        return_data: Callable[
            [Page, str, Literal['commit', 'domcontentloaded', 'load', 'networkidle'] | None, str | None],
            tuple[str | bytes, str, str],
        ]
        | None = None,
    ) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data and ETag.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.

        :raises ValueError: If there is a problem with the value supplied in one of the keys in the configuration file.
        :raises TypeError: If the value provided in one of the directives is not of the correct type.
        :raises ImportError: If the playwright package is not installed.
        :raises BrowserResponseError: If a browser error or an HTTP response code between 400 and 599 is received.
        :returns: The data retrieved and the ETag.
        """
        job_state._http_client_used = 'playwright'

        if self._delay:  # pragma: no cover  TODO not yet implemented.
            logger.debug(f'Delaying for {self._delay} seconds (duplicate network location)')
            time.sleep(self._delay)

        try:
            from playwright._repo_version import version as playwright_version
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import HttpCredentials, ProxySettings, Route, sync_playwright
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        except ImportError:  # pragma: no cover
            raise ImportError(
                f"Python package 'playwright' is not installed; cannot run jobs with the 'use_browser: true' "
                f"directive. Please install dependencies with 'pip install webchanges[use_browser]' and run again. "
                f'({job_state.job.get_indexed_location()})'
            ) from None

        try:
            import psutil
        except ImportError:  # pragma: no cover
            raise ImportError(
                f"Python package 'psutil' is not installed; cannot run jobs with the 'use_browser: true' "
                f"directive. Please install dependencies with 'pip install webchanges[use_browser]' and run again. "
                f'({job_state.job.get_indexed_location()})'
            ) from None

        # deprecations
        if self.navigate:
            raise ValueError(f"Job {job_state.job.index_number}: Directive 'navigate' is deprecated with Playwright.")
        if self.wait_for:
            raise ValueError(
                f"Job {job_state.job.index_number}: Directive 'wait_for' is deprecated with Playwright; replace with "
                f"'wait_for_function', 'wait_for_selector' or 'wait_for_timeout'."
            )
        if self.wait_until in {'networkidle0', 'networkidle2'}:
            warnings.warn(
                f"Job {self.index_number}: Value '{self.wait_until}' of the 'wait_until' directive is deprecated "
                f"with Playwright; for future compatibility replace it with 'networkidle'.",
                DeprecationWarning,
                stacklevel=1,
            )
            self.wait_until = 'networkidle'
        if self.wait_for_navigation:
            warnings.warn(
                f"Job {self.index_number}: Directive 'wait_for_navigation' is deprecated with Playwright; "
                "for future compatibility replace it with 'wait_for_url'.",
                DeprecationWarning,
                stacklevel=1,
            )
            if isinstance(self.wait_for_navigation, str):
                self.wait_for_url = self.wait_for_navigation
            else:
                warnings.warn(
                    f"Job {self.index_number}: Directive 'wait_for_navigation' is "
                    f'of type {type(self.wait_for_navigation).__name__} and cannot be converted for use with '
                    f"Playwright; please use 'wait_for_url' (see documentation)  ( {self.get_indexed_location()} ).",
                    DeprecationWarning,
                    stacklevel=1,
                )

        headers = self.get_headers(job_state, user_agent=None)

        if self.http_credentials:
            if not isinstance(self.http_credentials, str):
                raise ValueError(
                    f"Job {job_state.job.index_number}: Directive 'http_credentials' needs to be a string in the "
                    f'format username:password; found a {type(self.http_credentials).__name__}.'
                )
            creds_split: SplitResult = urlsplit(self.http_credentials)

            if creds_split.netloc:
                http_credentials: HttpCredentials = {
                    'username': creds_split.username or '',
                    'password': creds_split.password or '',
                    'origin': f'{creds_split.scheme}://{creds_split.netloc}',
                }
            else:
                if len(self.http_credentials.split(':')) != 2:
                    raise ValueError(
                        f'Job {job_state.job.index_number}: Directive http_credentials is malformed: '
                        f'{self.http_credentials}'
                    )
                http_credentials: HttpCredentials = {
                    'username': self.http_credentials.split(':')[0],
                    'password': self.http_credentials.split(':')[1],
                }

        else:
            http_credentials = None

        proxy_str = self.get_proxy()
        if proxy_str is not None:
            proxy_split: SplitResult | SplitResultBytes = urlsplit(proxy_str)
            proxy: ProxySettings | None = {
                'server': (
                    f'{proxy_split.scheme!s}://{proxy_split.hostname!s}:{proxy_split.port!s}'
                    if proxy_split.port
                    else ''
                ),
                'username': str(proxy_split.username),
                'password': str(proxy_split.password),
            }
            proxy_for_logging = proxy.copy()
            if proxy_for_logging['password']:
                proxy_for_logging['password'] = '*******'  # noqa: S105 possible hardcoded password
            logger.debug(f'Job {self.index_number}: Proxy: {proxy_for_logging}')
        else:
            proxy = None

        if self.switches:
            if isinstance(self.switches, str):
                self.switches = self.switches.split(',')
            if not isinstance(self.switches, list):
                raise TypeError(
                    f"Job {job_state.job.index_number}: Directive 'switches' needs to be a string or list; found a "
                    f'{type(self.switches).__name__} ( {self.get_indexed_location()} ).'
                )
            args: list[str] | None = [f'--{switch.removeprefix("--")}' for switch in self.switches]
            if not headless and logger.getEffectiveLevel() <= 10:  # logging.INFO
                args += ['--auto-open-devtools-for-tabs']

        else:
            args = (
                ['--auto-open-devtools-for-tabs']
                if not headless and logger.getEffectiveLevel() <= 10  # logging.DEBUG
                else None
            )

        if self.ignore_default_args:
            if isinstance(self.ignore_default_args, str):
                self.ignore_default_args = self.ignore_default_args.split(',')
            ignore_default_args = self.ignore_default_args
            if isinstance(ignore_default_args, list):
                ignore_default_args = [f'--{a.removeprefix("--")}' for a in ignore_default_args]
            elif not isinstance(self.ignore_default_args, bool):
                raise TypeError(
                    f"Job {job_state.job.index_number}: Directive 'ignore_default_args' needs to be a bool, string or "
                    f'list; found a {type(self.ignore_default_args).__name__} ( {self.get_indexed_location()} ).'
                )
        else:
            ignore_default_args = None

        timeout = self.timeout * 1000 if self.timeout else 120000  # Playwright's default of 30 seconds is too short

        # memory
        virtual_memory = psutil.virtual_memory().available
        swap_memory = psutil.swap_memory().free
        start_free_mem = virtual_memory + swap_memory
        logger.debug(
            f'Job {job_state.job.index_number}: Found {virtual_memory / 1e6:,.0f} MB of available physical memory '
            f'(plus {swap_memory / 1e6:,.0f} MB of swap) before launching the browser.'
        )

        # launch browser
        with ExitStack() as stack:
            p = stack.enter_context(sync_playwright())
            executable_path = os.getenv('WEBCHANGES_BROWSER_PATH')
            value = self.use_browser if isinstance(self.use_browser, str) else 'chrome'
            if value.startswith(('chrome', 'msedge')):
                browser_type = p.chromium
                channel = None if executable_path else value
            elif value == 'firefox':
                browser_type = p.firefox
                channel = None
            elif value == 'webkit':
                browser_type = p.webkit
                channel = None
            else:
                raise ValueError(
                    f"Job {job_state.job.index_number}: Directive 'use_browser' value {value!r} must be "
                    f"'firefox', 'webkit', or start with 'chrome' or 'msedge' "
                    f'( {self.get_indexed_location()} ).'
                )
            browser_name = executable_path or value
            no_viewport = False if not self.switches else any('--window-size' in switch for switch in self.switches)
            if not self.user_data_dir:
                browser = stack.enter_context(
                    browser_type.launch(
                        executable_path=executable_path,
                        channel=channel,
                        args=args,
                        ignore_default_args=ignore_default_args,
                        timeout=timeout,
                        headless=headless,
                        proxy=proxy,
                    )
                )
                browser_version = browser.version
                if browser_type is p.chromium:
                    default_user_agent = (
                        f'Mozilla/5.0 ({self.get_user_agent_platform()}) AppleWebKit/537.36 (KHTML, like Gecko) '
                        f'Chrome/{browser_version.split(".", maxsplit=1)[0]}.0.0.0 Safari/537.36'
                    )
                    user_agent = headers.pop('User-Agent', default_user_agent)
                else:
                    user_agent = headers.pop('User-Agent', None)
                context = stack.enter_context(
                    browser.new_context(
                        no_viewport=no_viewport,
                        ignore_https_errors=self.ignore_https_errors,
                        user_agent=user_agent,  # will be detected if in headers
                        extra_http_headers=dict(headers),
                        http_credentials=http_credentials,
                    )
                )
                logger.info(
                    f'Job {self.index_number}: Playwright {playwright_version} launched {browser_name.capitalize()} '
                    f'browser {browser_version}'
                )

            else:
                user_agent = headers.pop('User-Agent', '')

                context = stack.enter_context(
                    browser_type.launch_persistent_context(
                        user_data_dir=self.user_data_dir,
                        channel=channel,
                        executable_path=executable_path,
                        args=args,
                        ignore_default_args=ignore_default_args,
                        headless=headless,
                        proxy=proxy,
                        no_viewport=no_viewport,
                        ignore_https_errors=self.ignore_https_errors,
                        extra_http_headers=dict(headers),
                        user_agent=user_agent,  # will be detected if in headers
                        http_credentials=http_credentials,
                    )
                )
                browser_version = context.browser.version
                logger.info(
                    f'Job {self.index_number}: Playwright {playwright_version} launched {browser_name.capitalize()} '
                    f'browser from user data directory {self.user_data_dir}'
                )

            # the below to bypass detection; from https://intoli.com/blog/not-possible-to-block-chrome-headless/
            init_script = self.init_script or (
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined });"
                'window.chrome = {runtime: {},};'  # This is abbreviated: entire content is huge!!
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5] });"
            )
            context.add_init_script(init_script)

            # set default timeout
            context.set_default_timeout(timeout)

            # open a page
            page = context.new_page()

            url = self.url
            if self.initialization_url:
                logger.info(f'Job {self.index_number}: Initializing website by navigating to {self.initialization_url}')
                try:
                    response = page.goto(
                        self.initialization_url,
                        wait_until=self.wait_until,
                    )
                except PlaywrightError as e:
                    logger.info(f'Job {self.index_number}: Website initialization page returned error {e}')
                    if logger.root.level <= 20:  # logging.INFO
                        self._save_error_files(page)
                    raise

                if not response:
                    raise BrowserResponseError(('No response received from browser on initialization',))

                if self.initialization_js:
                    logger.info(f"Job {self.index_number}: Running init script '{self.initialization_js}'")
                    page.evaluate(self.initialization_js)
                    if self.wait_for_url:
                        logger.info(f'Job {self.index_number}: Waiting for page to navigate to {self.wait_for_url}')
                        page.wait_for_url(self.wait_for_url, wait_until=self.wait_until)
                updated_url = page.url
                init_url_params = dict(parse_qsl(urlparse(updated_url).params))
                try:
                    new_url = url.format(**init_url_params)
                except KeyError as e:
                    raise ValueError(  # noqa: B904
                        f"Job {job_state.job.index_number}: Directive 'initialization_url' did not find key"
                        f" {e} to substitute in 'url'."
                    )
                if new_url != url:
                    url = new_url
                    logger.info(f'Job {self.index_number}: URL updated to {url}')

            data = None
            if self.data:
                if not self.method:
                    self.method = 'POST'
                logger.info(f'Job {self.index_number}: Sending POST request to {url}')
                if 'Content-Type' not in headers:
                    headers['Content-Type'] = (
                        'application/json' if self.data_as_json else 'application/x-www-form-urlencoded'
                    )
                if isinstance(self.data, (dict, list)):
                    data = json.dumps(self.data, ensure_ascii=False) if self.data_as_json else urlencode(self.data)
                elif isinstance(self.data, str):
                    data = quote(self.data)
                else:
                    raise ValueError(
                        f"Job {job_state.job.index_number}: Directive 'data' needs to be a string, dictionary or list; "
                        f'found a {type(self.data).__name__} ( {self.get_indexed_location()} ).'
                    )

            if self.params is not None:
                if isinstance(self.params, (dict, list)):
                    params = urlencode(self.params)
                elif isinstance(self.params, str):
                    params = quote(self.params)
                else:
                    raise ValueError(
                        f"Job {job_state.job.index_number}: Directive 'params' needs to be a string, dictionary or "
                        f'list; found a {type(self.params).__name__} ( {self.get_indexed_location()} ).'
                    )
                url += f'?{params}'

            if self.method and self.method != 'GET':

                def handle_route(route: Route) -> None:
                    """Handler function to change the route (a pyee.EventEmitter callback)."""
                    logger.info(f'Job {self.index_number}: Intercepted route to change request method to {self.method}')
                    route.continue_(method=str(self.method), post_data=data)

                page.route(url, handler=handle_route)

            if self.block_elements:
                if isinstance(self.block_elements, str):
                    self.block_elements = self.block_elements.split(',')
                if not isinstance(self.block_elements, list):
                    raise TypeError(
                        f"'block_elements' needs to be a string or list, not {type(self.block_elements)} "
                        f'( {self.get_indexed_location()} )'
                    )
                playwright_request_resource_types = [
                    # https://playwright.dev/docs/api/class-request#request-resource-type
                    'document',
                    'stylesheet',
                    'image',
                    'media',
                    'font',
                    'script',
                    'texttrack',
                    'xhr',
                    'fetch',
                    'eventsource',
                    'websocket',
                    'manifest',
                    'other',
                ]
                for element in self.block_elements:
                    if element not in playwright_request_resource_types:
                        raise ValueError(
                            f"Unknown '{element}' resource type in 'block_elements' ( {self.get_indexed_location()} )"
                        )
                logger.info(f"Job {self.index_number}: Found 'block_elements' and adding a route to intercept elements")

                def handle_elements(route: Route) -> None:
                    """Handler function to block elements (a pyee.EventEmitter callback)."""
                    if route.request.resource_type in self.block_elements:  # ty:ignore[unsupported-operator]
                        logger.debug(
                            f'Job {self.index_number}: Intercepted retrieval of resource_type '
                            f"'{route.request.resource_type}' and aborting"
                        )
                        route.abort()
                    else:
                        route.continue_()

                page.route('**/*', handler=handle_elements)

            # navigate page
            logger.info(f'Job {self.index_number}: {browser_name.capitalize()} {browser_version} navigating to {url}')
            logger.debug(f'Job {self.index_number}: User agent {user_agent}')
            logger.debug(f'Job {self.index_number}: Extra headers {headers}')
            try:
                if return_data is not None:
                    logger.info(f"Job {self.index_number}: Using the 'return_data' Callable")
                    return return_data(page, url, self.wait_until, self.referer)  # ty:ignore[invalid-argument-type]
                if response_handler is not None:
                    logger.info(f"Job {self.index_number}: Using the 'response_handler' Callable")
                    response = response_handler(page, url, self.wait_until, self.referer)  # ty:ignore[invalid-argument-type]
                else:
                    response = page.goto(url, wait_until=self.wait_until, referer=self.referer)

                if not response:
                    raise BrowserResponseError(('No response received from browser on navigation',))

                if response.status == 304:
                    logger.debug(f'Job {self.index_number}: Intercepted response with {response.status} status')
                    raise NotModifiedError(response.status)

                if response.ok:
                    if self.wait_for_url:
                        logger.info(f'Job {self.index_number}: Waiting for page to navigate to {self.wait_for_url}')
                        if isinstance(self.wait_for_url, str):
                            page.wait_for_url(
                                self.wait_for_url,
                                wait_until=self.wait_until,
                                timeout=timeout,
                            )
                        elif isinstance(self.wait_for_url, dict):
                            page.wait_for_url(**self.wait_for_url)
                        else:
                            raise ValueError(
                                f"Job {job_state.job.index_number}: Directive 'wait_for_url' can only be a string or a "
                                f'dictionary; found a {type(self.wait_for_url.__name__)} '
                                f'( {self.get_indexed_location()} ).'
                            )
                    if self.wait_for_selector:
                        logger.info(f'Job {self.index_number}: Waiting for selector {self.wait_for_selector}')
                        if not isinstance(self.wait_for_selector, list):
                            self.wait_for_selector = [self.wait_for_selector]
                        for selector in self.wait_for_selector:
                            if isinstance(selector, str):
                                page.wait_for_selector(selector)
                            elif isinstance(selector, dict):
                                page.wait_for_selector(**selector)
                            else:
                                raise ValueError(
                                    f"Job {job_state.job.index_number}: Directive 'wait_for_selector' can only be a "
                                    f'string or a dictionary, or a list of these; found a '
                                    f'{type(self.wait_for_selector).__name__} ( {self.get_indexed_location()} ).'
                                )
                    if self.wait_for_function:
                        logger.info(f'Job {self.index_number}: Waiting for function {self.wait_for_function}')
                        if isinstance(self.wait_for_function, str):
                            page.wait_for_function(self.wait_for_function)
                        elif isinstance(self.wait_for_function, dict):
                            page.wait_for_function(**self.wait_for_function)
                        else:
                            raise ValueError(
                                f"Job {job_state.job.index_number}: Directive 'wait_for_function' can only be a string "
                                f'or a dictionary; found a {type(self.wait_for_function).__name__}'
                                f' ( {self.get_indexed_location()} ).'
                            )
                    if self.wait_for_timeout:
                        logger.info(f'Job {self.index_number}: Waiting for timeout {self.wait_for_timeout}')
                        if isinstance(self.wait_for_timeout, (int, float)) and not isinstance(
                            self.wait_for_timeout, bool
                        ):
                            page.wait_for_timeout(self.wait_for_timeout * 1000)
                        else:
                            raise ValueError(
                                f"Job {job_state.job.index_number}: Directive 'wait_for_timeout' can only be a number; "
                                f'found a {type(self.wait_for_timeout).__name__}'
                                f' ( {self.get_indexed_location()} ).'
                            )

                else:
                    logger.info(
                        f'Job {self.index_number}: Received response HTTP {response.status} {response.status_text} '
                        f'from {response.url}'
                    )
                    logger.debug(f'Job {self.index_number}: Response headers {response.all_headers()}')
                    message = response.status_text
                    if response.status != 404:
                        body = page.text_content('body')
                        if body is not None:
                            message = f'{message}\n{body.strip()}' if message else body.strip()

                    if response.status in (429, 500, 502, 503, 504):
                        logger.debug(f'Job {self.index_number}: Response error is transient.')
                        raise TransientHTTPError(message, status_code=response.status)

                    raise BrowserResponseError((message,), response.status)

                # extract content
                if content_handler is not None:
                    logger.info(f"Job {self.index_number}: Using the 'content_handler' Callable")
                    return content_handler(page)
                if self.evaluate is not None:
                    try:
                        content = page.evaluate(self.evaluate)
                    except PlaywrightError:
                        logger.error(
                            f'Job {self.index_number}: Received browser error when trying to evaluate {self.evaluate}'
                        )
                        logger.debug(page.content())
                        raise
                    if isinstance(content, str):
                        mime_type = 'text/plain'
                    elif isinstance(content, bytes):
                        mime_type = 'application/octet-stream'
                    else:
                        try:
                            content = json.dumps(content, ensure_ascii=False)
                            mime_type = 'application/json'
                        except TypeError:
                            content = str(content)
                            mime_type = 'text/plain'
                else:
                    content = page.content()
                    mime_type = response.header_value('content-type') or ''
                etag = response.header_value('etag') or ''
                virtual_memory = psutil.virtual_memory().available
                swap_memory = psutil.swap_memory().free
                used_mem = start_free_mem - (virtual_memory + swap_memory)
                logger.debug(
                    f'Job {job_state.job.index_number}: Found {virtual_memory / 1e6:,.0f} MB of available physical '
                    f'memory (plus {swap_memory / 1e6:,.0f} MB of swap) before closing the browser (a decrease of '
                    f'{used_mem / 1e6:,.0f} MB).'
                )

                # if no name directive is given, set to title tag if found in HTML or XML, truncated to 60 chars
                if not self.name and content:
                    title = re.search(r'<title.*?>(.+?)</title>', content)
                    if title:
                        self.name = html.unescape(title.group(1))[:60]

                return content, etag, mime_type

            except PlaywrightError as e:
                logger.error(f'Job {self.index_number}: Browser returned error {e}\n({url})')
                if isinstance(e, PlaywrightTimeoutError):
                    logger.debug(f'Job {self.index_number}: PlaywrightTimeoutError is transient')
                    raise TransientBrowserError('PlaywrightTimeoutError') from e
                chromium_error = str(e.args[0]).split()[-1]  # error format is 'Page.goto: net:: ...'
                if chromium_error in self.chromium_connection_errors:
                    logger.debug(f'Job {self.index_number}: Browser error {chromium_error} is transient')
                    raise TransientBrowserError(chromium_error) from e
                if logger.root.level <= 20:  # logging.INFO
                    self._save_error_files(page)
                raise

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        exception_str = str(exception).strip()
        if self.proxy and 'net::ERR' in exception_str:
            exception_str += f'\n\n(Job has proxy {self.proxy})'
            return exception_str
        return exception_str

    def ignore_error(self, exception: Exception) -> bool:
        """Determine whether the error of the job should be ignored.

        :param exception: The exception.
        :returns: True if the error should be ignored, False otherwise.
        """
        from playwright.sync_api import Error as PlaywrightError

        if self.ignore_connection_errors and (
            isinstance(exception, (PlaywrightError, TransientHTTPError, TransientBrowserError))
        ):
            return True
        if (
            self.ignore_timeout_errors
            and isinstance(exception, TransientBrowserError)
            and any(x in exception.args[0] for x in ('PlaywrightTimeoutError', 'net::ERR_TIMED_OUT'))
        ):
            return True
        if (
            self.ignore_too_many_redirects
            and isinstance(exception, TransientBrowserError)
            and exception.args[0] == 'net::ERR_TOO_MANY_REDIRECTS'
        ):
            return True
        if (
            self.ignore_http_error_codes
            and isinstance(exception, BrowserResponseError)
            and exception.status_code is not None
        ):
            return self._ignore_http_error_code(exception.status_code)

        return False
