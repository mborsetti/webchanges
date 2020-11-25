import asyncio
import logging
import os
import threading
from urllib.parse import urlsplit

from .cli import setup_logger

logger = logging.getLogger(__name__)


def get_proxy(url, http_proxy, https_proxy):
    """Returns proxy to be used and username + password"""
    # check if proxy is being used
    if urlsplit(url).scheme == 'http':
        proxy = http_proxy
    elif urlsplit(url).scheme == 'https':
        proxy = https_proxy
    else:
        proxy = None
    proxy_username = str(urlsplit(proxy).username) if urlsplit(proxy).username else None
    proxy_password = str(urlsplit(proxy).password) if urlsplit(proxy).password else None
    if proxy:
        proxy_server = f'{urlsplit(proxy).scheme}://{urlsplit(proxy).hostname}' + (
            f':{urlsplit(proxy).port}' if urlsplit(proxy).port else '')
    else:
        proxy_server = None

    return proxy_server, proxy_username, proxy_password


class BrowserLoop(object):
    def __init__(self, chromium_revision, proxy_server, ignore_https_errors, user_data_dir, switches):
        self._event_loop = asyncio.new_event_loop()
        self._browser = self._event_loop.run_until_complete(
            self._launch_browser(chromium_revision, proxy_server, ignore_https_errors, user_data_dir, switches))
        self._loop_thread = threading.Thread(target=self._event_loop.run_forever)
        self._loop_thread.start()

    async def _launch_browser(self, chromium_revision, proxy_server, ignore_https_errors, user_data_dir, switches):
        chromium_revision = str(chromium_revision) if chromium_revision else chromium_revision
        if chromium_revision:
            os.environ['PYPPETEER_CHROMIUM_REVISION'] = chromium_revision
        import pyppeteer

        args = []
        if proxy_server:
            args.append(f'--proxy-server={proxy_server}')
        if user_data_dir:
            args.append(f'--user-data-dir={os.path.expanduser(os.path.expandvars(user_data_dir))}')
        if switches:
            if isinstance(switches, str):
                switches = switches.split(',')
            args.extend(switches)
        browser = await pyppeteer.launch(ignoreHTTPSErrors=ignore_https_errors, args=args)
        for p in (await browser.pages()):
            await p.close()
        return browser

    async def _get_content(self, url, headers, cookies, timeout, proxy_username, proxy_password, wait_until,
                           wait_for):
        # context = await self._browser.createIncognitoBrowserContext()
        context = self._browser
        page = await context.newPage()
        if cookies:
            await page.setExtraHTTPHeaders({'Cookies': '; '.join([f'{k}={v}' for k, v in cookies.items()])})
        if headers:
            await page.setExtraHTTPHeaders(headers)
        if proxy_username or proxy_password:
            await page.authenticate({'username': proxy_username, 'password': proxy_password})
        options = {}
        if timeout:
            options['timeout'] = timeout * 1000
        if wait_until:
            options['waitUntil'] = wait_until
        await page.goto(url, options)
        if wait_for:
            if isinstance(wait_for, (int, float, complex)) and not isinstance(wait_for, bool):
                wait_for *= 1000
            await page.waitFor(wait_for)
        content = await page.content()
        await context.close()
        return content

    def process(self, url, headers, cookies, timeout, proxy_username, proxy_password, wait_until, wait_for):
        return asyncio.run_coroutine_threadsafe(
            self._get_content(url, headers, cookies, timeout, proxy_username, proxy_password, wait_until, wait_for),
            self._event_loop).result()

    def destroy(self):
        self._event_loop.call_soon_threadsafe(self._event_loop.stop)
        self._loop_thread.join()
        self._loop_thread = None
        self._event_loop.run_until_complete(self._browser.close())
        self._browser = None
        self._event_loop = None


class BrowserContext(object):
    _BROWSER_LOOP = None
    _BROWSER_LOCK = threading.Lock()
    _BROWSER_REFCNT = 0

    def __init__(self, chromium_revision, proxy_server, ignore_https_errors, user_data_dir, switches):
        with BrowserContext._BROWSER_LOCK:
            if BrowserContext._BROWSER_REFCNT == 0:
                logger.info('Creating browser main loop')
                BrowserContext._BROWSER_LOOP = BrowserLoop(chromium_revision, proxy_server, ignore_https_errors,
                                                           user_data_dir, switches)
            BrowserContext._BROWSER_REFCNT += 1

    def process(self, url, headers, cookies, timeout, proxy_username, proxy_password, wait_until, wait_for):
        return BrowserContext._BROWSER_LOOP.process(url, headers, cookies, timeout, proxy_username, proxy_password,
                                                    wait_until, wait_for)

    def close(self):
        with BrowserContext._BROWSER_LOCK:
            BrowserContext._BROWSER_REFCNT -= 1
            if BrowserContext._BROWSER_REFCNT == 0:
                logger.info('Destroying browser main loop')
                BrowserContext._BROWSER_LOOP.destroy()
                BrowserContext._BROWSER_LOOP = None


def main():
    import argparse
    import json

    # headers and cookies get passed as JSON; make sure to escape the double quotes, e.g.
    # browser.py --cookies {\"test\":\"test\"} or whatever works with the shell you're using
    parser = argparse.ArgumentParser(description='Browser handler')
    parser.add_argument('url', help='URL to retrieve')
    parser.add_argument('-v', '--verbose', action='store_true', help='show debug output')
    parser.add_argument('--chromium_revision', help='Chromium revision to use')
    parser.add_argument('--http_proxy', help='proxy to be used with http URLs')
    parser.add_argument('--https_proxy', help='proxy to be used with https URLs')
    parser.add_argument('--headers', help='HTTP headers in JSON format (escape double quotes etc.)', type=json.loads)
    parser.add_argument('--cookies', help='cookies in JSON format (escape double quotes etc.)', type=json.loads)
    parser.add_argument('--timeout', help='timeout in seconds')
    parser.add_argument('--ignore_https_errors', help='ignore HTTPS errors')
    parser.add_argument('--user_data_dir', help='the directory path of a Chromium user profile to use')
    parser.add_argument('--switches', help='additional Chromium switches, comma separated')
    parser.add_argument('--wait-until',
                        choices=['load', 'domcontentloaded', 'networkidle0', 'networkidle2'],
                        help='When pyppeteer considers a pageload finished')
    args = parser.parse_args()

    setup_logger(args.verbose)

    proxy_server, proxy_username, proxy_password = get_proxy(args.url, args.http_proxy, args.https_proxy)

    try:
        ctx = BrowserContext(args.chromium_revision, args.ignore_https_errors, proxy_server,
                             args.user_data_dir, args.switches)
        print(ctx.process(args.url, args.cookies, args.headers, args.timeout, proxy_password, proxy_username,
                          args.wait_until, args.wait_for))
    finally:
        ctx.close()


if __name__ == '__main__':
    main()
