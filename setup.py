from setuptools import setup, find_packages

setup(
    name='cymatic-visualizer',
    version='1.0.0',
    description='GPU-accelerated real-time cymatic audio visualizer',
    author='otherworlding',
    packages=find_packages(),
    python_requires='>=3.11',
    install_requires=[
        'pygame-ce>=2.5.0',
        'moderngl>=5.10.0',
        'numpy>=1.26.0',
        'sounddevice>=0.4.6',
        'soundfile>=0.12.1',
    ],
    entry_points={
        'console_scripts': ['cymatic=cymatic.__main__:main'],
    },
)
