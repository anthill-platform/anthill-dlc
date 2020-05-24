
from setuptools import setup, find_namespace_packages

DEPENDENCIES = [
    "anthill-common>=0.2.4"
]

setup(
    name='anthill-dlc',
    package_data={
      "anthill.dlc": ["anthill/dlc/sql", "anthill/dlc/static"]
    },
    version='0.2',
    description='Downloadable content (DLC) management service for Anthill platform',
    author='desertkun',
    license='MIT',
    author_email='desertkun@gmail.com',
    url='https://github.com/anthill-platform/anthill-dlc',
    namespace_packages=["anthill"],
    include_package_data=True,
    packages=find_namespace_packages(include=["anthill.*"]),
    zip_safe=False,
    install_requires=DEPENDENCIES
)
