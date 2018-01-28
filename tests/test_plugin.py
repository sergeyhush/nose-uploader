import json
import os
import random
import shutil
import string
import unittest

from nose.plugins import PluginTester

from nose_uploader.plugin import Uploader, UploadManager


def random_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def key_value(key, value):
    return "%s=%s" % (key, value)


run_id_key = 'INSTANCE'
run_id_val = 'test_{}'.format(random_generator())
run_id = key_value(run_id_key, run_id_val)

extra_id_key = random_generator(5)
extra_id_val = random_generator(10)
extra_id = key_value(extra_id_key, extra_id_val)

upload_vars = [run_id, extra_id]
upload_dir = 'test_results'
upload_url = 'http://localhost:8080/upload-test-results'
support = os.path.join(os.path.dirname(__file__), 'support')


@unittest.skip
class TestUploaderPluginJson(PluginTester, unittest.TestCase):
    activate = '--with-uploader'
    args = ['--nose-uploader-url=%s' % upload_dir,
            '--nose-uploader-vars=%s' % ','.join(upload_vars)]
    plugins = [Uploader()]
    suitepath = os.path.join(support, 'trdb')

    def runTest(self):
        print("x" * 70)
        print(str(self.output))
        print("x" * 70)

        assert 'ERROR: test_basic.test_error_exception' in self.output
        assert 'ERROR: test_basic.test_error_name_error' in self.output
        assert 'FAIL: test_basic.test_fail_assert' in self.output
        assert 'FAIL: test_basic.test_fail_assert_long_output' in self.output
        assert 'Ran 5 tests' in self.output
        for _file in os.listdir(upload_dir):
            if _file.endswith('.json'):
                with open(os.path.join(upload_dir, _file)) as fp:
                    result = json.load(fp)
                    self.assertIn(run_id_key, result)
                    self.assertEqual(result[run_id_key], run_id_val)
                    self.assertIn(extra_id_key, result)
                    self.assertEqual(result[extra_id_key], extra_id_val)

    def tearDown(self):
        shutil.rmtree(upload_dir)


class TestUploaderPluginHttp(PluginTester, unittest.TestCase):
    activate = '--with-uploader'
    args = ['--nose-uploader-url=%s' % upload_url, '--nose-uploader-vars=%s' % run_id]
    plugins = [Uploader()]
    suitepath = os.path.join(support, 'trdb')

    def setUp(self):
        self._uploaded_results = []
        mockUploadManager = UploadManager
        mockUploadManager.upload = lambda s, x: self._uploaded_results.append(x)

        super(TestUploaderPluginHttp, self).setUp()

    def runTest(self):
        self.assertEqual(len(self._uploaded_results), 5)
        self.assertEqual(self._uploaded_results[0]['stdout'], 'I am stdout\n')


if __name__ == '__main__':
    unittest.main()
