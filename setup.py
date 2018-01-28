import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command

NAME = 'nose-uploader'
VERSION = '0.0.1'
DESCRIPTION = 'Nose test result uploader'
URL = 'https://stash.cumulusnetworks.com/users/sergey/nose-uploader'
EMAIL = 'sergey@sudakovich.com'
AUTHOR = 'Sergey Sudakovich'

REQUIRED = [
    'nose==1.3.4', 'requests', 'six'
]
TEST_REQUIRED = [
    'mock'
]

here = os.path.abspath(os.path.dirname(__file__))


class UploadCommand(Command):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """Prints things in bold."""
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPi via Twine')
        os.system('twine upload dist/*')

        sys.exit()


setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    packages=find_packages(exclude=["tests"]),
    entry_points={
        'nose.plugins.0.10': ['nose_uploader = nose_uploader.plugin:Uploader']
    },
    install_requires=REQUIRED,
    tests_requires=TEST_REQUIRED,
    include_package_data=True,
    cmdclass={
        'upload': UploadCommand,
    },
)
