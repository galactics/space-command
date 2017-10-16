# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

install_requires = [
    'beyond',
    'peewee',
    'requests',
    'aiohttp',
    'docopt',
    'matplotlib'
]

version = "0.1"

setup(
    name='space-command',
    version=version,
    description="Space Command",
    platforms=["any"],
    keywords=['flight dynamic', 'satellite', 'space'],
    author='Jules David',
    author_email='jules@onada.fr',
    license='GPLv3',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 2 - Pre-Alpha"
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Topic :: Scientific/Engineering :: Astronomy",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            "space = spacecmd.main:main"
        ]
    }
)
