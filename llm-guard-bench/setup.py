"""
Setup configuration for LLM Guard Bench.
Installs the package with all required dependencies.
"""

from setuptools import setup, find_packages

setup(
    name="llm-guard-bench",
    version="1.0.0",
    description="LLM Guard Bench: Adversarial Attack Benchmark Framework for Language Models",
    author="Security Team",
    python_requires=">=3.9",
    packages=find_packages(),
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "aiohttp>=3.8.0",
        "aiosqlite>=0.17.0",
        "groq>=0.4.0",
        "matplotlib>=3.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "llm-guard-bench=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
