"""Test the generation of various types of diffs."""
from webchanges.handler import JobState
from webchanges.jobs import ShellJob
from webchanges.storage import CacheSQLite3Storage

cache_storage = CacheSQLite3Storage(':memory:')
job_state = JobState(cache_storage, ShellJob(command=''))
job_state.old_timestamp = 1605147837.511478  # initial release of webchanges!
job_state.new_timestamp = 1605147837.511478


def test_generate_diff_normal():
    """Base case."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    expected = ['@@ -1 +1 @@', '-a', '+b']
    diff = job_state._generate_diff()
    assert diff.splitlines()[2:] == expected


def test_generate_diff_additions_only():
    """Changed line with "additions" comparison_filter."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.additions_only = True
    expected = ['/**Comparison type: Additions only**', '@@ -1 +1 @@', '+b']
    diff = job_state._generate_diff()
    assert diff.splitlines()[2:] == expected


def test_generate_diff_additions_only_new_lines():
    """Change of new empty lines with "additions" comparison_filter."""
    job_state.old_data = 'a\nb'
    job_state.new_data = 'a\n\nb\n'
    job_state.job.additions_only = True
    job_state.verb = 'changed'
    diff = job_state._generate_diff()
    assert not diff
    assert job_state.verb == 'changed,no_report'


def test_generate_diff_deletions_only():
    """Changed line with "deletions" comparison_filter."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'b\n'
    job_state.job.additions_only = False
    job_state.job.deletions_only = True
    expected = ['/**Comparison type: Deletions only**', '@@ -1 +1 @@', '-a']
    diff = job_state._generate_diff()
    assert diff.splitlines()[2:] == expected


def test_generate_diff_deletions_only_only_removed_lines():
    """Changed line with "deletions" comparison_filter."""
    job_state.old_data = 'a\n\nb\n'
    job_state.new_data = 'a\nb'
    job_state.job.additions_only = False
    job_state.job.deletions_only = True
    job_state.verb = 'changed'
    diff = job_state._generate_diff()
    assert not diff
    assert job_state.verb == 'changed,no_report'


def test_generate_diff_additions_only_75pct_deleted():
    """'additions' comparison_filter with 75% or more of original content deleted."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'd\n'
    job_state.job.additions_only = True
    expected = [
        '/**Comparison type: Additions only**',
        '/**Deletions are being shown as 75% or more of the content has been deleted**',
        '@@ -1,3 +0,0 @@',
        '-a',
        '-b',
        '-c',
    ]
    diff = job_state._generate_diff()
    assert diff.splitlines()[2:] == expected


def test_generate_diff_additions_only_deletions():
    """'additions' comparison_filter and lines were only deleted."""
    job_state.old_data = 'a\nb\nc\nd\n'
    job_state.new_data = 'a\nb\nc\n'
    job_state.job.additions_only = True
    assert job_state._generate_diff() == ''


def test_generate_diff_deletions_only_additions():
    """'deletions' comparison_filter and lines were only added."""
    job_state.old_data = 'a\n'
    job_state.new_data = 'a\nb\n'
    job_state.job.additions_only = False
    job_state.job.deletions_only = True
    assert job_state._generate_diff() == ''
