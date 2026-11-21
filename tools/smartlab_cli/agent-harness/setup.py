"""cli-anything-smartlab - read-only Smart Lab CLI (CLI-Anything methodology, PEP 420 namespace package)."""
from setuptools import find_namespace_packages, setup

setup(
    name="cli-anything-smartlab",
    version="0.1.0",
    description="Read-only, agent-native CLI for the Smart Research Lab (devices, ESP32, cameras, AI, knowledge, n8n definitions, git).",
    long_description=open("cli_anything/smartlab/README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    packages=find_namespace_packages(include=["cli_anything.*"]),
    package_data={"cli_anything.smartlab": ["skills/*.md", "README.md", "tests/TEST.md"]},
    python_requires=">=3.10",
    install_requires=["click>=8.1", "prompt-toolkit>=3.0"],
    extras_require={"test": ["pytest>=7"]},
    entry_points={"console_scripts": [
        "cli-anything-smartlab=cli_anything.smartlab.smartlab_cli:main",
        "smartlab=cli_anything.smartlab.smartlab_cli:main",
    ]},
)
