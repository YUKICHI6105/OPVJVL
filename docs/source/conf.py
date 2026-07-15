# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'OPVJVL 太陽電池と発光素子計測プログラム'
copyright = '2026, Ishii & Fukagawa Lab (Chiba University). Developed with AI-assistance (Claude by Anthropic).'
author = 'Ishii & Fukagawa Lab (Chiba University)'

from utils.version import __version__
version = '.'.join(__version__.split('.')[:2])
release = __version__

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.mathjax',
    'sphinx_fontawesome',
    'myst_parser',
]

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

# 本ドキュメントのビルド環境(共有venv)にはPyQt6/pyqtgraph/pyserial/PyVISAが
# 実インストールされているため、autodocは実環境でモジュールをimportして
# シグネチャ・docstringを取得する(モック化不要)。
autodoc_mock_imports = []

intersphinx_mapping = {
    'python': ('https://docs.python.org/ja/3', None),
}

numfig = True


templates_path = ['_templates']
exclude_patterns = []
add_module_names = False

# 数式の表示位置を左寄せ（インデント2em）に設定
mathjax3_config = {
    'chtml': {
        'displayAlign': 'left',
        'displayIndent': '2em'
    }
}

language = 'ja'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_show_sourcelink = False
html_static_path = ['_static']
html_css_files = ['custom.css']

# 外部ライブラリ（PyQt6等）のパースエラー警告を抑制する
suppress_warnings = [
    'autodoc.import_object',
    'docutils',
    'ref.python',
    'duplicate_declaration',
    'ref.duplicate_obj_description',  # pyqtSignalの重複登録警告を抑制
]

def setup(app):
    def skip_member(app, what, name, obj, skip, options):
        # pyqtSignal や pyqtBoundSignal は Attributes セクションに記載されているため、
        # 重複ドキュメント化を防止するためにメンバ自体の自動生成をスキップします。
        obj_type_str = str(type(obj))
        if "pyqtSignal" in obj_type_str or "pyqtBoundSignal" in obj_type_str:
            return True
        # autodoc_mock_imports でモック化されたオブジェクトの場合、
        # 戻り値は Sphinx の _MockObject になります。
        # _MockObject は __sphinx_mock__ = True を持つため、これで確実に検出できます。
        if what == 'class' and getattr(obj, '__sphinx_mock__', False):
            return True
        return skip

    app.connect('autodoc-skip-member', skip_member)
