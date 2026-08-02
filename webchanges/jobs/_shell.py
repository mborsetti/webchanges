"""ShellJob — run a shell command and capture its output."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import re
import subprocess
from typing import TYPE_CHECKING

from webchanges.filters import FilterBase
from webchanges.jobs._base import Job

if TYPE_CHECKING:
    from webchanges.handler import JobState

logger = logging.getLogger(__name__)

# A Python interpreter, optionally with a version suffix, an extension, and/or a path (e.g. 'python', 'python3',
# 'python3.14', '/usr/bin/python3', r'C:\Program Files\Python\python.exe').
PYTHON_RE = re.compile(r'(?:^|[\\/])python3?(?:\.\d+)?(?:\.exe)?$', re.IGNORECASE)
# A short-form verbosity flag, e.g. '-v', '-vv', '-vvv'.
SHORT_VERBOSE_RE = re.compile(r'-(v+)')
# The long-form verbosity flag.
LONG_VERBOSE = '--verbose'
# Characters that separate one shell command from the next (pipes, chaining, redirections, subshells).
SHELL_OPERATORS = frozenset('|&;<>()')


def _logger_verbosity() -> int:
    """Derive the verbosity (i.e. the number of -v's) that webchanges was run with from the logger's effective level.

    A Job has no access to the CommandConfig, but the effective logging level set by cli.setup_logger() is a faithful
    proxy for it (this is the inverse of the mapping done there).

    :returns: The number of -v's webchanges was run with: 0 (none), 1 (-v), 2 (-vv) or 3 (-vvv or higher).
    """
    level = logger.getEffectiveLevel()
    if level == logging.NOTSET:  # 0 (-vvv)
        return 3
    if level <= logging.DEBUG:  # 10 (-vv)
        return 2
    if level <= logging.INFO:  # 20 (-v)
        return 1
    return 0  # WARNING or higher, i.e. webchanges was run without -v


def _tokenize(command: str) -> list[tuple[int, int, str, bool]]:
    """Split a shell command line into tokens, keeping track of where each one is located in the original string.

    Quoting is honored, so that shell operators and flags appearing inside a quoted string (e.g. the code of a
    'python -c' invocation) are not mistaken for shell syntax.  A backslash is NOT treated as an escape character, as
    on Windows it is the path separator.  Runs of shell operator characters are returned as a single token, so that
    '&&', '||' and '>>' are kept whole, as is the file descriptor prefixing a redirection (the '2' of '2>'), which is
    part of it rather than an argument of the command being redirected.

    :param command: The shell command line.
    :returns: A list of (start, end, text, is_operator) tuples, where start and end are the token's offsets into
       command, text is the token with any quotes removed, and is_operator tells whether the token is a shell
       operator (as opposed to a word).
    """
    tokens: list[tuple[int, int, str, bool]] = []
    i = 0
    while i < len(command):
        if command[i].isspace():
            i += 1
            continue

        start = i
        if command[i] in SHELL_OPERATORS:
            while i < len(command) and command[i] in SHELL_OPERATORS:
                i += 1
            tokens.append((start, i, command[start:i], True))
            continue

        quote = ''
        text: list[str] = []
        while i < len(command):
            char = command[i]
            if quote:  # inside a quoted string: everything is literal until the matching quote
                if char == quote:
                    quote = ''
                else:
                    text.append(char)
            elif char in {'"', "'"}:
                quote = char
            elif char.isspace() or char in SHELL_OPERATORS:
                break
            else:
                text.append(char)
            i += 1

        # A number immediately followed by a redirection is the file descriptor being redirected (e.g. the '2' of
        # '2> err.txt'); it is part of the redirection, not an argument of the command.
        word = ''.join(text)
        is_file_descriptor = word.isdigit() and i < len(command) and command[i] in {'<', '>'}
        tokens.append((start, i, word, is_file_descriptor))

    return tokens


def _add_python_verbosity(command: str, verbosity: int) -> str:
    """Add (or raise) the verbosity flag of any Python interpreter invoked by a shell command line.

    Each command in the command line (they are separated by shell operators such as '|', '&&' or a redirection) whose
    first token is a Python interpreter has its verbosity flag raised to verbosity.  An existing flag is never removed
    or lowered: a command already carrying '--verbose', or a '-v...' of verbosity or higher, is left untouched.  The
    flag is added at the END of the invocation (i.e. where the script or module being run will see it), never right
    after the interpreter, as '-v' there is Python's own trace-imports flag.  The code string of a '-c' invocation is
    skipped, so a '-v' inside it is neither detected nor modified.

    :param command: The shell command line.
    :param verbosity: The number of -v's to raise each Python invocation to; if 0, command is returned unchanged.
    :returns: The shell command line, with verbosity flags added or raised.
    """
    if verbosity < 1:  # webchanges was run without -v: the overwhelmingly common case
        return command

    # Group the word tokens into commands, i.e. split them at the shell operators.
    commands: list[list[tuple[int, int, str]]] = [[]]
    for start, end, text, is_operator in _tokenize(command):
        if is_operator:
            commands.append([])
        else:
            commands[-1].append((start, end, text))

    # Compute at most one edit (start, end, replacement) per command; an empty range is an insertion.
    edits: list[tuple[int, int, str]] = []
    flag = f'-{"v" * verbosity}'
    for tokens in commands:
        if not tokens or not PYTHON_RE.search(tokens[0][2]):  # not a Python interpreter invocation
            continue
        edits.extend(_python_verbosity_edit(tokens, verbosity, flag))

    # Apply the edits from the last to the first, so that the offsets of those not yet applied remain valid.
    for start, end, replacement in reversed(edits):
        command = f'{command[:start]}{replacement}{command[end:]}'

    return command


def _python_verbosity_edit(tokens: list[tuple[int, int, str]], verbosity: int, flag: str) -> list[tuple[int, int, str]]:
    """Compute the edit required to raise a single Python invocation to verbosity.  Called by _add_python_verbosity().

    :param tokens: The (start, end, text) word tokens of the invocation, the first one being the interpreter.
    :param verbosity: The number of -v's to raise the invocation to.
    :param flag: The verbosity flag to add, i.e. verbosity number of v's.
    :returns: A list with the single (start, end, replacement) edit required, or an empty list if none is.
    """
    skip_next = False
    for start, end, text in tokens[1:]:
        if skip_next:  # the code string of a '-c' invocation: opaque to us
            skip_next = False
            continue
        if text == '-c':
            skip_next = True
            continue
        if text == LONG_VERBOSE:  # already verbose; we never remove or lower a flag
            return []
        match = SHORT_VERBOSE_RE.fullmatch(text)
        if match:
            if len(match.group(1)) >= verbosity:  # already at or above the wanted verbosity; never lower it
                return []
            return [(start, end, flag)]  # raise the existing flag in place

    end_of_invocation = tokens[-1][1]
    return [(end_of_invocation, end_of_invocation, f' {flag}')]


class ShellJob(Job):
    """Run a shell command and get its standard output."""

    __kind__ = 'command'

    __required__: tuple[str, ...] = ('command',)
    __optional__: tuple[str, ...] = (
        'stderr',  # ignored; here for backwards compatibility
    )

    def get_location(self) -> str:
        """Get the 'location' of the job, i.e. the command.

        :returns: The command of the job.
        """
        return self.user_visible_url or self.command

    def set_base_location(self, location: str) -> None:
        """Sets the job's location (command or url) to location.  Used for changing location (uuid)."""
        self.command = location
        self.guid = self.get_guid()

    def retrieve(self, job_state: JobState, headless: bool = True) -> tuple[str | bytes, str, str]:
        """Runs job to retrieve the data, and returns data, ETag (which is blank) and mime_type (also blank).

        If webchanges is being run verbosely (-v, -vv or -vvv), the matching verbosity flag is passed on to any Python
        interpreter invoked by the command (see :func:`_add_python_verbosity`).

        The command's stdin is connected to the null device, so a command that unexpectedly prompts for input reads
        EOF and errors out instead of hanging the job forever.

        :param job_state: The JobState object, to keep track of the state of the retrieval.
        :param headless: For browser-based jobs, whether headless mode should be used.
        :returns: The data retrieved and the ETag and mime_type.
        :raises subprocess.CalledProcessError: Subclass of SubprocessError, raised when a process returns a non-zero
           exit status.
        :raises subprocess.TimeoutExpired: Subclass of SubprocessError, raised when a timeout expires while waiting for
           a child process.
        """
        logger.info('Job %s: Running shell command: %s', self.index_number, self.command)
        needs_bytes = FilterBase.filter_chain_needs_bytes(self.filters)  # ty:ignore[invalid-argument-type]

        # deprecations
        if self.stderr:
            raise ValueError(f"Job {job_state.job.index_number}: Directive 'stderr' is deprecated and does nothing.")

        # Pass the verbosity webchanges was run with (-v, -vv or -vvv) on to any Python interpreter invoked by the
        # command.  Never modifies self.command, as it is what the job's guid is computed from.
        command = _add_python_verbosity(self.command, _logger_verbosity())
        if command != self.command:
            logger.info('Job %s: Passing verbosity on to Python; running instead: %s', self.index_number, command)

        try:
            # stdin is DEVNULL so that a command unexpectedly prompting for input (e.g. Python's input()) fails
            # immediately with a visible error instead of hanging forever waiting on the inherited console stdin.
            response = subprocess.run(  # noqa: S602 `shell=True`, security issue
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                shell=True,
                check=True,
                text=(not needs_bytes),
            )
        except subprocess.CalledProcessError as e:
            logger.info(f'Job {self.index_number}: Command: {e.cmd} ')
            logger.info(f'Job {self.index_number}: Failed with returncode {e.returncode}')
            logger.info(f'Job {self.index_number}: stderr : {e.stderr}')
            logger.info(f'Job {self.index_number}: stdout : {e.stdout}')
            raise
        return (response.stdout, '', 'application/octet-stream' if needs_bytes else 'text/plain')

    def format_error(self, exception: Exception, tb: str) -> str:
        """Format the error of the job if one is encountered.

        :param exception: The exception.
        :param tb: The traceback.format_exc() string.
        :returns: A string to display and/or use in reports.
        """
        if isinstance(exception, subprocess.CalledProcessError):
            # Instead of a full traceback, just show the HTTP error
            return (
                f'Error: Exit status {exception.returncode} returned from subprocess:\n'
                f'{(exception.stderr or exception.stdout).strip()}'
            )
        if isinstance(exception, FileNotFoundError):
            return f'Error returned by OS: {str(exception).strip()}'
        return tb
