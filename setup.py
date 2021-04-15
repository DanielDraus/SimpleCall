from setuptools import setup, find_packages

with open('README.md') as file_:
    long_description = file_.read()

install_requires = [line.rstrip('\n') for line in open('requirements.txt')]
setup(
    name='simple_call',
    version='1.0.3',
    packages=find_packages(),
    license='Public',
    author='draus',
    author_email='danieldraus1@interia.pl',
    description='SimpleCall',
    long_description=long_description,
    include_package_data=True,
    install_requires=install_requires
)
