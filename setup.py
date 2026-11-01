from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="fazeradock",
    version="1.0.0",
    author="FAZENA Team",
    description="Era of Accessible, User-Friendly Molecular Docking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MrEgorin/fazeradock",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Intended Audience :: Science/Research",
    ],
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.20",
        "matplotlib>=3.5",
        "PyQt5>=5.15",
    ],
    extras_require={
        "bio": ["biopython>=1.80"],
    },
    entry_points={
        "console_scripts": [
            "fazeradock=fazeradock.gui.main_window:main",
        ],
    },
)
