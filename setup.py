from setuptools import setup, find_packages

with open('README.md') as file_:
    long_description = file_.read()

install_requires = [line.rstrip('\n') for line in open('requirements.txt')]
setup(
    name='hran_IV8',
    version='1.0.3',
    packages=find_packages(),
    license='For Nokia Internal Use',
    author='draus',
    author_email='daniel.draus@nokia.com',
    description='HRAN SimpleCall',
    long_description=long_description,
    include_package_data=True,
    install_requires=install_requires
)
