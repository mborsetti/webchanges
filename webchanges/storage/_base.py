"""Base storage classes."""

# The code below is subject to the license contained in the LICENSE.md file, which is part of the source code.

from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml

from webchanges import __docs_url__
from webchanges.filters import FilterBase
from webchanges.jobs import JobBase, ShellJob
from webchanges.util import edit_file, file_ownership_checks

logger = logging.getLogger(__name__)


# Custom YAML constructor for !include
def yaml_include(loader: yaml.SafeLoader, node: yaml.Node) -> list[Any]:
    file_path = Path(loader.name).parent.joinpath(node.value)
    with file_path.open('r') as f:
        return list(yaml.safe_load_all(f))


# Add the custom constructor to the YAML loader
yaml.add_constructor('!include', yaml_include, Loader=yaml.SafeLoader)


class BaseStorage(ABC):  # noqa:  B024 abstract base class, but it has no abstract methods or properties
    """Base class for storage."""


class BaseFileStorage(BaseStorage, ABC):
    """Base class for file storage."""

    def __init__(self, filename: str | Path) -> None:
        """:param filename: The filename or directory name to storage."""
        if isinstance(filename, str):
            self.filename = Path(filename)
        else:
            self.filename = filename


class BaseTextualFileStorage(BaseFileStorage, ABC):
    """Base class for textual files."""

    def __init__(self, filename: str | Path) -> None:
        """:param filename: The filename or directory name to storage."""
        super().__init__(filename)

    @abstractmethod
    def load(self, *args: Any) -> Any:  # noqa: ANN401 Dynamically typed expressions (typing.Any) are disallowed
        """Load from storage.

        :param args: Specified by the subclass.
        :return: Specified by the subclass.
        """

    @abstractmethod
    def save(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401 Dynamically typed expressions (typing.Any) are disallowed
        """Save to storage.

        :param args: Specified by the subclass.
        :param kwargs: Specified by the subclass.
        :return: Specified by the subclass.
        """

    @classmethod
    @abstractmethod
    def parse(cls, filename: Path) -> Any:  # noqa: ANN401 Dynamically typed expressions (typing.Any) are disallowed
        """Parse storage contents.

        :param filename: The filename.
        :return: Specified by the subclass.
        """

    def edit(self) -> int:
        """Edit file.

        :returns: None if edit is successful, 1 otherwise.
        """
        # Similar code to UrlwatchCommand.edit_hooks()
        logger.debug(f'Edit file {self.filename}')
        if isinstance(self.filename, list):
            if len(self.filename) > 1:
                raise ValueError(f'Only one jobs file can be specified for editing; found {len(self.filename)}.')
            filename = self.filename[0]
        else:
            filename = self.filename
        file_edit = filename.with_stem(filename.stem + '_edit')

        if filename.is_file():
            shutil.copy(filename, file_edit)

        while True:
            try:
                edit_file(file_edit)
                # Check if we can still parse it
                if self.parse is not None:
                    self.parse(file_edit)
                break  # stop if no exception on parser
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001 Do not catch blind exception: `Exception`
                print()
                print('Errors in updating file:')
                print('======')
                print(e)
                print('======')
                print()
                print(f'The file {filename} was NOT updated.')
                user_input = input('Do you want to retry the same edit? [Y/n] ')
                if not user_input or user_input.lower().startswith('y'):
                    continue
                file_edit.unlink()
                print('No changes have been saved.')
                return 1

        if filename.is_symlink():
            filename.write_text(file_edit.read_text())
        else:
            file_edit.replace(filename)
        file_edit.unlink(missing_ok=True)
        print('Saved edits in', filename)
        return 0


class JobsBaseFileStorage(BaseTextualFileStorage, ABC):
    """Class for jobs textual files storage."""

    filename: list[Path]

    def __init__(self, filename: list[Path]) -> None:
        """Class for jobs textual files storage.

        :param filename: The filenames of the jobs file.
        """
        super().__init__(filename)  # ty:ignore[invalid-argument-type]
        self.filename = filename

    def load_secure(self) -> list[JobBase]:
        """Load the jobs from a text file checking that the file is secure (i.e. belongs to the current UID and only
        the owner can write to it - Linux only).

        :return: List of JobBase objects.
        """
        jobs: list[JobBase] = self.load()

        def is_shell_job(job: JobBase) -> bool:
            """Check if the job uses filter 'shellpipe' or an external differ, as they call
            subprocess.run(shell=True) (insecure).

            :returns: True if subprocess.run(shell=True) is invoked by job, False otherwise.
            """
            if isinstance(job, ShellJob):
                return True

            for filter_kind, _ in FilterBase.normalize_filter_list(job.filters, job.index_number):  # ty:ignore[invalid-argument-type]
                if filter_kind == 'shellpipe':
                    return True

                if job.differ and job.differ.get('name') == 'command':
                    return True

            return False

        shelljob_errors = []
        for file in self.filename:
            shelljob_errors.extend(file_ownership_checks(file))
        removed_jobs = (job for job in jobs if is_shell_job(job))
        if shelljob_errors and any(removed_jobs):
            print(
                f'ERROR: Removing the following jobs because '
                f' {" and ".join(shelljob_errors)}: {" ,".join(str(job.index_number) for job in removed_jobs)}\n'
                f'(see {__docs_url__}en/stable/jobs.html#important-note-for-command-jobs).'
            )
            jobs = [job for job in jobs if job not in removed_jobs]

        logger.info(f'Loaded {len(jobs)} jobs from {", ".join(str(file) for file in self.filename)}.')
        return jobs


class BaseYamlFileStorage(BaseTextualFileStorage, ABC):
    """Base class for YAML textual files storage."""

    @classmethod
    def parse(cls, filename: Path) -> Any:  # noqa: ANN401 Dynamically typed expressions (typing.Any) are disallowed
        """Return contents of YAML file if it exists

        :param filename: The filename Path.
        :return: Specified by the subclass.
        """
        if filename is not None and filename.is_file():
            with filename.open() as fp:
                return yaml.safe_load(fp)
        return None
