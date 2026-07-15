import setuptools

setuptools.setup(
    name="simple_config",
    version="1.0.2",
    author="Lautus Solutions LLC",
    author_email="sjsmal07@gmail.com",
    packages=["simple_config"],
    scripts=[],
    url="https://github.com/stevelautus/simple_config/",
    license="Apache-2.0",
    description="Simple configuration handling utility for Python services with multiple modes of execution",
    long_description=open("README.md").read(),
    install_requires=[
        "PyYAML>=6.0",
        "python-dateutil>=2.8.2",
        "boto3>=1.29.7",
    ],
)
