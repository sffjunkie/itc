# Copyright 2009-2012, Simon Kennedy, code@sffjunkie.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from os.path import join
from distutils.core import setup

setup(name='itc',
    version='0.3.3',
    description='Extracts images from an iTunes .itc file.',
    long_description="""A small script which extracts PNG, JPEG and ARGB
    cover art from an iTunes `.itc` file.""",
    author='Simon Kennedy',
    author_email='code@sffjunkie.co.uk',
    url="http://www.sffjunkie.co.uk/python-itc.html",
    license='Apache-2.0',
    scripts=[join('itc', 'itc.py')],
)
