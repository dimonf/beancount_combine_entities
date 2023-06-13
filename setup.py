from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

#from my_pip_package import __version__

requirements = ["beancount"]

setup(
    name = "beancount_combine_entities",
    version = __version__,
    author  = "Dmitri Kourbatsky",
    author_email = "camel109@gmail.com",
    description = "A beancount plugin, which combines records of two separate entities",
    long_description = long_description,
    long_description_content_type = "text/markdown",
    url = "https://github.com/dimonf/beancount_combine_entities",
    install_requires = requirements,
    python_required=">=3.6"
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={'beancount_combine_entities':'src'}
)

