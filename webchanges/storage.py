import copy
import logging
import os
import shutil
import stat
from abc import ABCMeta, abstractmethod

import minidb

import webchanges as project

try:
    import msgpack
except ImportError:
    msgpack = None

try:
    import redis
except ImportError:
    redis = None

import yaml

from .filters import FilterBase
from .jobs import JobBase, ShellJob, UrlJob
from .util import atomic_rename, edit_file

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    'display': {  # select whether the report include the categories below
        'new': True,
        'error': True,
        'unchanged': False,
    },

    'report': {
        # text, html and markdown are three content types of reports
        'html': {
            'diff': 'unified',  # 'unified' or 'table'
            'diff_numlines': None,  # default if None
        },

        'text': {
            'line_length': 75,
            'details': True,
            'footer': True,
            'minimal': False,
        },

        'markdown': {
            'details': True,
            'footer': True,
            'minimal': False,
        },

        # the keys below control where a report is displayed and/or sent

        'stdout': {  # the console / command line display
            'enabled': True,
            'color': True,
        },

        'browser': {  # the system's default browser
            'enabled': False,
            'title': f'[{project.__project_name__}] {{count}} changes: {{jobs}}'
        },

        'email': {  # email (except mailgun)
            'enabled': False,
            'html': True,
            'to': '',
            'from': '',
            'subject': f'[{project.__project_name__}] {{count}} changes: {{jobs}}',
            'method': 'smtp',  # either 'smtp' or 'sendmail'
            'smtp': {
                'host': 'localhost',
                'user': '',
                'port': 25,
                'starttls': True,
                'auth': True,
                'insecure_password': '',
            },
            'sendmail': {
                'path': 'sendmail',
            }
        },
        'pushover': {
            'enabled': False,
            'app': '',
            'device': None,
            'sound': 'spacealarm',
            'user': '',
            'priority': 'normal',
        },
        'pushbullet': {
            'enabled': False,
            'api_key': '',
        },
        'telegram': {
            'enabled': False,
            'bot_token': '',
            'chat_id': '',
        },
        'webhook': {
            'enabled': False,
            'webhook_url': '',
            'max_message_length': '',
        },
        'webhook_markdown': {
            'enabled': False,
            'webhook_url': '',
            'max_message_length': '',
        },
        'matrix': {
            'enabled': False,
            'homeserver': '',
            'access_token': '',
            'room_id': '',
        },
        'mailgun': {
            'enabled': False,
            'region': 'us',
            'api_key': '',
            'domain': '',
            'from_mail': '',
            'from_name': '',
            'to': '',
            'subject': '{count} changes: {jobs}'
        },
        'ifttt': {
            'enabled': False,
            'key': '',
            'event': '',
        },
        'xmpp': {
            'enabled': False,
            'sender': '',
            'recipient': '',
        },
    },

    'job_defaults': {  # default settings for jobs
        'all': {},
        'url': {},  # these are used for url jobs without use_browser
        'browser': {},  # these are used for url jobs with use_browser: true
        # TODO rename 'shell' to 'command' for clarity
        'shell': {},  # these are used for 'command' jobs
    }
}


def merge(source, destination):
    # https://stackoverflow.com/a/20666342
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge(value, node)
        else:
            destination[key] = value

    return destination


def get_current_user():
    try:
        return os.getlogin()
    except OSError:
        # If there is no controlling terminal, because urlwatch is launched by
        # cron, or by a systemd.service for example, os.getlogin() fails with:
        # OSError: [Errno 25] Inappropriate ioctl for device
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name


class BaseStorage(metaclass=ABCMeta):
    @abstractmethod
    def load(self, *args):
        ...

    @abstractmethod
    def save(self, *args):
        ...


class BaseFileStorage(BaseStorage, metaclass=ABCMeta):
    def __init__(self, filename):
        self.filename = filename


class BaseTextualFileStorage(BaseFileStorage, metaclass=ABCMeta):
    def __init__(self, filename):
        super().__init__(filename)
        self.config = {}
        self.load()

    @classmethod
    @abstractmethod
    def parse(cls, *args):
        ...

    def edit(self, example_file=None):
        fn_base, fn_ext = os.path.splitext(self.filename)
        file_edit = fn_base + '.edit' + fn_ext

        if os.path.exists(self.filename):
            shutil.copy(self.filename, file_edit)
        elif example_file is not None and os.path.exists(example_file):
            shutil.copy(example_file, file_edit)

        while True:
            try:
                edit_file(file_edit)
                # Check if we can still parse it
                if self.parse is not None:
                    self.parse(file_edit)
                break  # stop if no exception on parser
            except SystemExit:
                raise
            except Exception as e:
                print()
                print('Errors in file:')
                print('======')
                print(e)
                print('======')
                print('')
                print('The file', file_edit, 'was NOT updated.')
                user_input = input('Do you want to retry the same edit? (Y/n)')
                if not user_input or user_input.lower()[0] == 'y':
                    continue
                print('Your changes have been saved in', file_edit)
                return 1

        atomic_rename(file_edit, self.filename)
        print('Saving edit changes in', self.filename)
        return 0

    @classmethod
    def write_default_config(cls, filename):
        config_storage = cls(None)
        config_storage.filename = filename
        config_storage.save()


class JobsBaseFileStorage(BaseTextualFileStorage, metaclass=ABCMeta):
    def __init__(self, filename):
        self.filename = filename

    def shelljob_security_checks(self):

        if os.name == 'nt':
            return []

        shelljob_errors = []
        current_uid = os.getuid()

        dirname = os.path.dirname(self.filename) or '.'
        dir_st = os.stat(dirname)
        if (dir_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
            shelljob_errors.append(f'{dirname} is group/world-writable')
        if dir_st.st_uid != current_uid:
            shelljob_errors.append(f'{dirname} not owned by {get_current_user()}')

        file_st = os.stat(self.filename)
        if (file_st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)) != 0:
            shelljob_errors.append(f'{self.filename} is group/world-writable')
        if file_st.st_uid != current_uid:
            shelljob_errors.append(f'{self.filename} not owned by {get_current_user()}')

        return shelljob_errors

    def load_secure(self):
        jobs = self.load()

        def is_shell_job(job):
            if isinstance(job, ShellJob):
                return True

            for filter_kind, subfilter in FilterBase.normalize_filter_list(job.filter):
                if filter_kind == 'shellpipe':
                    return True

                if job.diff_tool is not None:
                    return True

            return False

        # Security checks for shell jobs - only execute if the current UID
        # is the same as the file/directory owner and only owner can write
        shelljob_errors = self.shelljob_security_checks()
        if shelljob_errors and any(is_shell_job(job) for job in jobs):
            print(f"Removing shell jobs, because {' and '.join(shelljob_errors)}")
            jobs = [job for job in jobs if not is_shell_job(job)]

        return jobs


class BaseTxtFileStorage(BaseTextualFileStorage, metaclass=ABCMeta):
    @classmethod
    def parse(cls, *args):
        filename = args[0]
        if filename is not None and os.path.exists(filename):
            with open(filename) as fp:
                for line in fp:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if line.startswith('|'):
                        yield ShellJob(command=line[1:])
                    else:
                        args = line.split(None, 2)
                        if len(args) == 1:
                            yield UrlJob(url=args[0])
                        elif len(args) == 2:
                            yield UrlJob(url=args[0], post=args[1])
                        else:
                            raise ValueError(f'Unsupported line format: {line}')


class BaseYamlFileStorage(BaseTextualFileStorage, metaclass=ABCMeta):
    @classmethod
    def parse(cls, *args):
        filename = args[0]
        if filename is not None and os.path.exists(filename):
            with open(filename) as fp:
                return yaml.safe_load(fp)


class YamlConfigStorage(BaseYamlFileStorage):
    def load(self, *args):
        self.config = merge(self.parse(self.filename) or {}, copy.deepcopy(DEFAULT_CONFIG))

    def save(self, *args):
        with open(self.filename, 'w') as fp:
            yaml.safe_dump(self.config, fp, default_flow_style=False, sort_keys=False)


class JobsYaml(BaseYamlFileStorage, JobsBaseFileStorage):

    @classmethod
    def parse(cls, *args):
        filename = args[0]
        if filename is not None and os.path.exists(filename):
            with open(filename) as fp:
                return [JobBase.unserialize(job) for job in yaml.safe_load_all(fp)
                        if job is not None]

    def save(self, *args):
        jobs = args[0]
        print(f'Saving updated list to {self.filename}')

        with open(self.filename, 'w') as fp:
            yaml.safe_dump_all([job.serialize() for job in jobs], fp, default_flow_style=False, sort_keys=False)

    def load(self, *args):
        with open(self.filename) as fp:
            return [JobBase.unserialize(job) for job in yaml.safe_load_all(fp) if job is not None]


class CacheStorage(BaseFileStorage, metaclass=ABCMeta):
    @abstractmethod
    def close(self):
        ...

    @abstractmethod
    def get_guids(self):
        ...

    @abstractmethod
    def load(self, job, guid):
        ...

    @abstractmethod
    def save(self, job, guid, data, timestamp, tries, etag=None):
        ...

    @abstractmethod
    def delete(self, guid):
        ...

    @abstractmethod
    def clean(self, guid):
        ...

    def backup(self):
        for guid in self.get_guids():
            data, timestamp, tries, etag = self.load(None, guid)
            yield guid, data, timestamp, tries, etag

    def restore(self, entries):
        for guid, data, timestamp, tries, etag in entries:
            self.save(None, guid, data, timestamp, tries, etag)

    def gc(self, known_guids):
        for guid in set(self.get_guids()) - set(known_guids):
            print(f'Removing: {guid}')
            self.delete(guid)

        for guid in known_guids:
            count = self.clean(guid)
            if count > 0:
                print(f'Removed {count} old versions of {guid}')


class CacheDirStorage(CacheStorage):
    def __init__(self, filename):
        super().__init__(filename)
        if not os.path.exists(filename):
            os.makedirs(filename)

    def close(self):
        #  No need to close
        return 0

    def _get_filename(self, guid):
        return os.path.join(self.filename, guid)

    def get_guids(self):
        return os.listdir(self.filename)

    def load(self, job, guid):
        filename = self._get_filename(guid)
        if not os.path.exists(filename):
            return None, None, None, None

        try:
            with open(filename) as fp:
                data = fp.read()
        except UnicodeDecodeError:
            with open(filename, 'rb') as fp:
                data = fp.read().decode('utf-8', 'ignore')

        timestamp = os.stat(filename)[stat.ST_MTIME]

        return data, timestamp, None, None

    def save(self, job, guid, data, timestamp, etag=None):
        # Timestamp and ETag are always ignored
        filename = self._get_filename(guid)
        with open(filename, 'w+') as fp:
            fp.write(data)

    def delete(self, guid):
        filename = self._get_filename(guid)
        if os.path.exists(filename):
            os.unlink(filename)

    def clean(self, guid):
        # We only store the latest version, no need to clean
        return 0


class CacheEntry(minidb.Model):
    guid = str
    timestamp = int
    data = str
    tries = int
    etag = str


class CacheMiniDBStorage(CacheStorage):
    def __init__(self, filename):
        super().__init__(filename)

        dirname = os.path.dirname(filename)
        if dirname and not os.path.isdir(dirname):
            os.makedirs(dirname)
# TODO BACKUP FILE
        if os.path.isfile(filename):
            import shutil
            _ = shutil.copy2(filename, filename + '.bak')
# TODO END BACKUP FILE
        self.db = minidb.Store(self.filename, debug=True)
        self.db.register(CacheEntry)

    def close(self):
        self.db.close()
        self.db = None

    def get_guids(self):
        return (guid for guid, in CacheEntry.query(self.db, minidb.Function('distinct', CacheEntry.c.guid)))

    def load(self, job, guid):
        for data, timestamp, tries, etag in CacheEntry.query(self.db,
                                                             CacheEntry.c.data // CacheEntry.c.timestamp
                                                             // CacheEntry.c.tries // CacheEntry.c.etag,
                                                             order_by=minidb.columns(CacheEntry.c.timestamp.desc,
                                                                                     CacheEntry.c.tries.desc),
                                                             where=CacheEntry.c.guid == guid, limit=1):
            return data, timestamp, tries, etag

        return None, None, 0, None

    def get_history_data(self, guid, count=1):
        history = {}
        if count < 1:
            return history
        for data, timestamp in CacheEntry.query(self.db, CacheEntry.c.data // CacheEntry.c.timestamp,
                                                order_by=minidb.columns(CacheEntry.c.timestamp.desc,
                                                                        CacheEntry.c.tries.desc),
                                                where=(CacheEntry.c.guid == guid)
                                                & ((CacheEntry.c.tries == 0) | (CacheEntry.c.tries == None))):  # noqa:E501,E711 comparison to None should be 'if cond is None:
            if data not in history:
                history[data] = timestamp
                if len(history) >= count:
                    break
        return history

    def save(self, job, guid, data, timestamp, tries, etag=None):
        self.db.save(CacheEntry(guid=guid, timestamp=timestamp, data=data, tries=tries, etag=etag))
        self.db.commit()

    def delete(self, guid):
        CacheEntry.delete_where(self.db, CacheEntry.c.guid == guid)
        self.db.commit()

    def clean(self, guid):
        keep_id = next((CacheEntry.query(self.db, CacheEntry.c.id, where=CacheEntry.c.guid == guid,
                                         order_by=CacheEntry.c.timestamp.desc, limit=1)), (None,))[0]

        if keep_id is not None:
            result = CacheEntry.delete_where(self.db, (CacheEntry.c.guid == guid) & (CacheEntry.c.id != keep_id))
            self.db.commit()
            return result

        return 0


class CacheRedisStorage(CacheStorage):
    def __init__(self, filename):
        super().__init__(filename)

        if redis is None or msgpack is None:
            raise ImportError('redis + msgpack are missing')

        self.db = redis.from_url(filename)

    def _make_key(self, guid):
        return 'guid:' + guid

    def close(self):
        self.db.connection_pool.disconnect()
        self.db = None

    def get_guids(self):
        guids = []
        for guid in self.db.keys(b'guid:*'):
            guids.append(str(guid[len('guid:'):]))
        return guids

    def load(self, job, guid):
        key = self._make_key(guid)
        data = self.db.lindex(key, 0)

        if data:
            r = msgpack.unpackb(data)
            return r['data'], r['timestamp'], r['tries'], r['etag']

        return None, None, 0, None

    def get_history_data(self, guid, count=1):
        history = {}
        if count < 1:
            return history

        key = self._make_key(guid)
        for i in range(0, self.db.llen(key)):
            r = self.db.lindex(key, i)
            c = msgpack.unpackb(r)
            if (c['tries'] == 0 or c['tries'] is None):
                if c['data'] not in history:
                    history[c['data']] = c['timestamp']
                    if len(history) >= count:
                        break
        return history

    def save(self, job, guid, data, timestamp, tries, etag=None):
        r = {
            'data': data,
            'timestamp': timestamp,
            'tries': tries,
            'etag': etag,
        }
        self.db.lpush(self._make_key(guid), msgpack.packb(r, use_bin_type=True))

    def delete(self, guid):
        self.db.delete(self._make_key(guid))

    def clean(self, guid):
        key = self._make_key(guid)
        i = self.db.llen(key)
        if self.db.ltrim(key, 0, 0):
            return i - self.db.llen(key)

        return 0


class CacheSQLite3Storage(CacheStorage):
    def __init__(self, filename):
        super().__init__(filename)
        import sqlite3
        self.db = sqlite3.connect(filename)

    def _make_key(self, guid):
        return 'guid:' + guid

    def close(self):
        self.db.close()
        self.db = None

    def get_guids(self):
        guids = []
        for guid in self.db.keys(b'guid:*'):
            guids.append(str(guid[len('guid:'):]))
        return guids

    def load(self, job, guid):
        key = self._make_key(guid)
        data = self.db.lindex(key, 0)

        if data:
            r = msgpack.unpackb(data)
            return r['data'], r['timestamp'], r['tries'], r['etag']

        return None, None, 0, None

    def get_history_data(self, guid, count=1):
        history = {}
        if count < 1:
            return history

        key = self._make_key(guid)
        for i in range(0, self.db.llen(key)):
            r = self.db.lindex(key, i)
            c = msgpack.unpackb(r)
            if (c['tries'] == 0 or c['tries'] is None):
                if c['data'] not in history:
                    history[c['data']] = c['timestamp']
                    if len(history) >= count:
                        break
        return history

    def save(self, job, guid, data, timestamp, tries, etag=None):
        r = {
            'data': data,
            'timestamp': timestamp,
            'tries': tries,
            'etag': etag,
        }
        self.db.lpush(self._make_key(guid), msgpack.packb(r, use_bin_type=True))

    def delete(self, guid):
        self.db.delete(self._make_key(guid))

    def clean(self, guid):
        key = self._make_key(guid)
        i = self.db.llen(key)
        if self.db.ltrim(key, 0, 0):
            return i - self.db.llen(key)

        return 0
