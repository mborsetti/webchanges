import os
from glob import glob

from flake8.api import legacy as flake8


def test_flake8():
    """Test that we conform to PEP-8"""
    style_guide = flake8.get_style_guide(ignore=['A', 'W503'])
    py_files = [y for x in os.walk(os.path.abspath('webchanges')) for y in glob(os.path.join(x[0], '*.py'))]
    report = style_guide.check_files(py_files)
    assert report.get_statistics('E') == [], 'Flake8 found violations'


def test_package_versions():
    import importlib
    print('\nPackage versions:')
    for package in sorted((
        'appdirs', 'cssselect', 'html2text', 'lxml', 'markdown2', 'minidb', 'yaml', 'requests', 'colorama',
        'pyppeteer', 'bs4', 'jsbeautifier', 'cssbeautifier', 'pdf2text', 'pytesseract', 'PIL', 'vobject',
        'chump', 'pushbullet', 'matrix_client', 'aioxmpp', 'msgpack', 'redis', 'keyring', 'pytest', 'coverage',
        'flake8', 'flake8-import-order', 'docutils', 'sphinx_rtd_theme', 'sphinx'), key=str.casefold):
        try:
            print(f"{package}=={importlib.import_module(package, '__version__').__version__}")
        except:
            print(f"{package} not installed")
    print()
