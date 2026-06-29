from setuptools import find_packages, setup

setup(
    name="photo-slideshow",
    version="0.1.0",
    packages=find_packages(include=["slideshow", "slideshow.*"]),
    install_requires=[
        "moviepy>=1.0.3",
        "Pillow>=10.0.0",
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.29.0",
    ],
    entry_points={
        "console_scripts": [
            "photo-slideshow=slideshow.cli:main",
        ],
    },
    python_requires=">=3.9",
)
