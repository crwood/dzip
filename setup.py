import setuptools

setuptools.setup(
    name="dzip",
    version="0.1",
    description="Make and extract deterministic zip archives.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Christopher R. Wood",
    license="MIT",
    url="https://github.com/crwood/dzip",
    keywords="deterministic zip archive",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Environment :: MacOS X",
        "Environment :: Win32 (MS Windows)",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: DFSG approved",
        "License :: OSI Approved",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Security",
        "Topic :: Security :: Cryptography",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Archiving",
        "Topic :: System :: Archiving :: Compression",
        "Topic :: System :: Archiving :: Packaging",
        "Topic :: Utilities",
    ],
    python_requires=">=2.7",
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    entry_points={"console_scripts": ["dzip=dzip.dzip:main",]},
)
