from setuptools import setup, find_packages
import os
# io.open is needed for projects that support Python 2.7
# It ensures open() defaults to text mode with universal newlines,
# and accepts an argument to specify the text encoding
# Python 3 only projects can skip this import
from io import open

import versioneer


here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


setup(
    name='grocery_helpers',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    description='Selenium-based Python API for online grocery retailers.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords='selenium grocery groceries food',
    author='Ryan Fobel',
    author_email='ryan@fobel.net',
    url='https://github.com/ryanfobel/grocery-helpers',
    install_requires=[
        'numpy',
        'pandas',
        'selenium',
    ],    
    license='BSD-3',    
)