from setuptools import setup, find_packages

setup(
    name="file-llm-translation",
    version="1.0.0",
    description="A program that translates long game files using LLM APIs",
    author="ghsdfkdfhkj",
    packages=find_packages(),
    install_requires=[
        "openai",
        "anthropic",
        "google-generativeai",
        "tkinterdnd2",
        "python-dotenv"
    ],
    entry_points={
        'console_scripts': [
            'file-llm-translation=main:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
) 