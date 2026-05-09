from pathlib import Path

from setuptools import find_packages, setup

PROJECT_ROOT = Path(__file__).parent


def get_version() -> str:
    init_file = PROJECT_ROOT / 'idf_drivers_gdb' / '__init__.py'
    for line in init_file.read_text(encoding='utf-8').splitlines():
        if line.startswith('__version__'):
            return line.split('=', 1)[1].strip().strip('"\'')
    raise RuntimeError('Unable to find package version')


setup(
    name='idf-drivers-gdb',
    version=get_version(),
    author='Espressif Systems',
    author_email='srmao@espressif.com',
    description='Python GDB commands for debugging ESP-IDF drivers',
    license='Apache-2.0',
    license_files=['LICENSE'],
    long_description_content_type='text/markdown',
    long_description=(PROJECT_ROOT / 'README.md').read_text(encoding='utf-8'),
    url='https://github.com/espressif/idf-drivers-gdb',
    project_urls={
        'Source': 'https://github.com/espressif/idf-drivers-gdb',
        'Issues': 'https://github.com/espressif/idf-drivers-gdb/issues',
    },
    packages=find_packages(include=['idf_drivers_gdb', 'idf_drivers_gdb.*']),
    package_data={'idf_drivers_gdb': ['py.typed']},
    install_requires=['term-image'],
    python_requires='>=3.10',
    keywords=['python', 'espressif'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Environment :: Console',
        'Topic :: Software Development :: Embedded Systems',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: MacOS :: MacOS X',
    ],
)
