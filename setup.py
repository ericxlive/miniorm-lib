from setuptools import setup, find_packages

setup(
    name="miniorm",  # Package name used in `import miniorm`
    version="0.1.0",  # Initial version
    description="A lightweight reflection-based ORM for PostgreSQL in Python",
    author="Eric de Sousa",  # Replace with your actual name or organization
    packages=find_packages(),  # Automatically discovers all packages under `miniorm/`
    include_package_data=True,  # Includes files specified in MANIFEST.in (if any)
    install_requires=[
        "psycopg2-binary",  # Required dependency to connect to PostgreSQL
    ],
    python_requires=">=3.11,<3.12",  # Minimum Python version supported
)