#from distutils.core import setup
from setuptools import setup, find_packages
from bkutils.common.version import bk_ver

setup(name="bk_flash",
    version=bk_ver,
    description="Beken flash download tool",
    author="beken",
    author_email="",
    maintainer="beken",
    maintainer_email="zhu.su@bekencorp.com",
    url="",
    license="MIT",
    install_requires=["pyserial", "click", "pyyaml", "pycryptodome"],
    platforms=["Windows", "GNU/Linux", "Darwin"],
    packages=find_packages(),
    data_files=[('config','config/flash_info.yml')],
    scripts=['bk_loader.py', 'tizen_entrance.py'])
