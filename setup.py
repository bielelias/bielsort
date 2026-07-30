"""Build configuration for the native extension.

Project metadata lives in pyproject.toml. Keeping setup.py limited to the
Extension object is supported by setuptools and avoids deprecated direct
setup.py commands.
"""

import sys

from setuptools import Extension, setup


compile_args = ["/O2"] if sys.platform == "win32" else ["-O3"]

setup(
    ext_modules=[
        Extension(
            "bielsort_native._bielsort",
            sources=["src/bielsort_native/_bielsort.c"],
            extra_compile_args=compile_args,
        )
    ],
)
