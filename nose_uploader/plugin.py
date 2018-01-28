import datetime
import json
import logging
import os
import sys
import traceback
from io import StringIO

import requests
from nose.plugins import Plugin
from nose.pyversion import force_unicode, format_exception
from nose.util import tolist
from six.moves.urllib.parse import urlparse

log = logging.getLogger(__name__)


def env_vars(prefix):
    """
    Return environment variables starting with prefix

    :param prefix:
    :return: dict
    """
    return {k: v for k, v in os.environ.items() if k.startswith(prefix)}


def now():
    """Return current time in UTC"""
    return datetime.datetime.utcnow()


class APIError(Exception):
    pass


class DataError(Exception):
    pass


# From nose/plugins/xunit.py
class Tee(object):
    def __init__(self, encoding, *args):
        self.encoding = encoding
        self._streams = args
        self.errors = None

    def write(self, data):
        data = force_unicode(data, self.encoding)
        for s in self._streams:
            s.write(data)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        for s in self._streams:
            s.flush()

    def isatty(self):
        return False


class Uploader(Plugin):
    """Test result uploader nose plugin"""
    name = 'uploader'
    encoding = 'UTF-8'
    env_prefix = 'NOSE_UPLOADER'

    def __init__(self):
        super(Uploader, self).__init__()

        self._capture_stack = []
        self._currentStdout = None
        self._currentStderr = None

    def options(self, parser, env):
        Plugin.options(self, parser, env)
        parser.add_option(
            '--nose-uploader-url',
            action='store',
            dest='nose_uploader_url',
            metavar='URL',
            default=env.get('NOSE_UPLOADER_URL'),
            help=("URL to where the test results should be uploaded."
                  "It can be local path as well as remote url."
                  "Default is current working directory json files."
                  "[NOSE_UPLOADER_URL]"))
        parser.add_option(
            '--nose-uploader-user',
            action='store',
            dest='nose_uploader_user',
            metavar='USER',
            default=env.get('NOSE_UPLOADER_USER'),
            help=("Upload server username."
                  "Used only when NOSE_UPLOADER_URL is an http(s) link."
                  "[NOSE_UPLOADER_USER]"))
        parser.add_option(
            '--nose-uploader-pass',
            action='store',
            dest='nose_uploader_pass',
            metavar='PASSWORD',
            default=env.get('NOSE_UPLOADER_PASS'),
            help=("Upload server password."
                  "Used only when NOSE_UPLOADER_PASS is an http(s) link."
                  "[NOSE_UPLOADER_PASS]"))
        parser.add_option(
            '--nose-uploader-vars',
            action='append',
            dest='nose_uploader_vars',
            metavar='PAIR',
            help=("Additional variables included with with test result upload."
                  "The format is a key=value pair"))

    def configure(self, options, conf):
        Plugin.configure(self, options, conf)

        self._nose_uploader_url = options.nose_uploader_url
        self._nose_uploader_user = options.nose_uploader_user
        self._nose_uploader_pass = options.nose_uploader_pass
        self._nose_uploader_vars = {}
        if options.nose_uploader_vars:
            std_vars = tolist(options.nose_uploader_vars)
            for var in std_vars:
                for pair in var.strip().split(","):
                    if not pair:
                        continue
                    items = pair.split("=", 1)
                    if len(items) > 1:
                        # "name=value"
                        key, value = items
                        self._nose_uploader_vars[key] = value
        # Include env variables that start wit 'NOSE_UPLOADER'
        self._nose_uploader_vars.update(env_vars(self.env_prefix))

    def _startCapture(self):
        self._capture_stack.append((sys.stdout, sys.stderr))
        self._currentStdout = StringIO()
        self._currentStderr = StringIO()
        sys.stdout = Tee(self.encoding, self._currentStdout, sys.stdout)
        sys.stderr = Tee(self.encoding, self._currentStderr, sys.stderr)

    def _endCapture(self):
        if self._capture_stack:
            sys.stdout, sys.stderr = self._capture_stack.pop()

    def _captured(self, stream):
        if stream:
            value = stream.getvalue()
            if value:
                return value
        return ''

    def _getCapturedStdout(self):
        return self._captured(self._currentStdout)

    def _getCapturedStderr(self):
        return self._captured(self._currentStderr)

    def beforeTest(self, test):
        self._test_start = now()
        self._startCapture()

    def afterTest(self, test):
        self._endCapture()
        self._currentStdout = None
        self._currentStderr = None

    def finalize(self, result):
        while self._capture_stack:
            self._endCapture()

    def addSuccess(self, test):
        self.send_result({
            'name': str(test),
            'status': 'pass',
        })

    def addFailure(self, test, err):
        self.send_result({
            'name': str(test),
            'status': 'fail',
            'traceback': format_exception(err),
            'stdout': self._getCapturedStdout(),
            'stderr': self._getCapturedStderr(),
        })

    def addError(self, test, err):
        self.send_result({
            'name': str(test),
            'status': 'error',
            'traceback': format_exception(err),
            'stdout': self._getCapturedStdout(),
            'stderr': self._getCapturedStderr(),
        })

    def format_error(self, err):
        exctype, value, tb = err
        return ''.join(traceback.format_exception(exctype, value, tb))

    def send_result(self, result):
        result['stop'] = now().isoformat()

        if not hasattr(self, '_test_start'):
            # test died before it ran (probably in setup())
            # just fake start/stop time so duration is zero
            result['start'] = result['stop']
        else:
            result['start'] = self._test_start.isoformat()

        result.update(self._nose_uploader_vars)
        UploadManager(self._nose_uploader_url).upload(result)

    def _start(self):
        self._startCapture()


class UploadManager(object):
    POST_FILE_KEY = 'test_file'

    def __init__(self, url, user=None, password=None):
        self.url = url if url is not None else ''
        self.upload_url = urlparse(self.url)
        self.upload_user = user
        self.upload_pass = password
        if self.upload_url.scheme.startswith('http'):
            self.upload_method = self.save_to_http
        elif not self.upload_url.scheme or self.upload_url.scheme == 'file':
            self.upload_method = self.save_to_json_file

        if not self.upload_method:
            raise Exception(
                "No upload method for scheme '%s'" % self.upload_url.scheme)

    def upload(self, result):
        self.upload_method(result)

    def _validate(self, data):
        """Validate incoming data"""

    def save_to_json_file(self, data, ext='json'):
        output_path = self.upload_url.path or '.'

        if not os.path.isdir(output_path):
            os.makedirs(output_path)

        output_filepath = os.path.join(output_path, "%s.%s" % (data['name'],
                                                               ext))

        log.debug("Output_filepath %s", output_filepath)

        if output_filepath:
            with open(output_filepath, 'w') as fp:
                json.dump(data, fp)

    def save_to_http(self, data):
        user = self.upload_user
        password = self.upload_pass
        auth = (user, password) if user or password else None

        try:
            response = requests.post(
                self.url,
                auth=auth,
                files={self.POST_FILE_KEY: ('test', json.dumps(data).decode('utf-8'))})
            response.raise_for_status()
        except requests.ConnectionError:
            raise APIError("Could not connect to upload server")
        except requests.exceptions.HTTPError as ex:
            raise APIError(ex)
