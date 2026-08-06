"""Build configuration for the native extension.

Project metadata lives in pyproject.toml. Keeping setup.py limited to the
Extension object is supported by setuptools and avoids deprecated direct
setup.py commands.
"""

import os
import sys

from setuptools import Extension, setup


sanitizers_enabled = os.environ.get("BIELSORT_SANITIZE") == "1"

if sys.platform == "win32":
    if sanitizers_enabled:
        raise RuntimeError("BIELSORT_SANITIZE is supported only on Unix")
    compile_args = ["/O2"]
    link_args = []
elif sanitizers_enabled:
    sanitizer_flags = ["-fsanitize=address,undefined"]
    compile_args = [
        "-O1",
        "-g",
        "-fno-omit-frame-pointer",
        *sanitizer_flags,
    ]
    link_args = sanitizer_flags
else:
    compile_args = ["-O3"]
    link_args = []

setup(
    ext_modules=[
        Extension(
            "bielsort_native._bielsort",
            sources=[
                "src/bielsort_native/_argsort.c",
                "src/bielsort_native/_bielsort.c",
                "src/bielsort_native/_streaming_topk.c",
            ],
            extra_compile_args=compile_args,
            extra_link_args=link_args,
        )
    ],
)
