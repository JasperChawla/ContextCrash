from setuptools import find_packages, setup

setup(
    name="contextcrash",
    version="0.1.0",
    description="LLM reliability benchmarking for RAG pipelines",
    python_requires=">=3.11",
    packages=find_packages(exclude=["tests*", "frontend*"]),
    install_requires=[
        "litellm>=1.40.0",
        "anthropic>=0.30.0",
        "duckdb>=0.10.0",
        "pydantic>=2.7.0",
        "pyyaml>=6.0.1",
        "fastapi>=0.111.0",
        "uvicorn[standard]>=0.30.0",
        "click>=8.1.7",
        "rich>=13.7.1",
        "tenacity>=8.3.0",
        "httpx>=0.27.0",
        "python-dotenv>=1.0.1",
    ],
    entry_points={
        "console_scripts": [
            "contextcrash=cli.main:main",
        ],
    },
)
