from setuptools import setup
from Cython.Build import cythonize

setup(
    name='Blackbox Library',
    ext_modules=cythonize(r"C:\Coding\optimized_ notebookjs\stealth_engine_v1\blackbox.py", compiler_directives={'language_level': "3"}),
)