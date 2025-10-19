import os
import shutil
from setuptools import setup, find_packages
from setuptools.command.install import install

class PostInstallCommand(install):
    def run(self):
        install.run(self)
        # Define the paths
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, ".mcp-open-client", "config")
        default_theme_src = os.path.join("mcp_open_client", "settings", "app-styles.css")
        default_theme_dst = os.path.join(config_dir, "user_theme.css")

        # Create the config directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)

        # Copy the default theme CSS file
        if os.path.exists(default_theme_src):
            shutil.copy2(default_theme_src, default_theme_dst)
            print(f"Copied default theme to {default_theme_dst}")
        else:
            print(f"Warning: Could not find default theme at {default_theme_src}")

setup(
    name="mcp-open-client",
    version="0.4.5",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "nicegui",
        "openai",
        "jsonschema",
        "requests",
        "fastmcp>=2.8.1"
    ],
    entry_points={
        "console_scripts": [
            "mcp-open-client=mcp_open_client.cli:main",
        ],
    },
    python_requires=">=3.7",
    description="MCP Open Client - A NiceGUI-based chat application for Claude",
    author="alejoair",
    author_email="your.email@example.com",
    url="https://github.com/alejoair/mcp-open-client",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_data={
        "mcp_open_client": [
            "settings/*.css",
            "settings/*.json",
            "ui/*.py",
        ],
    },
    cmdclass={
        'install': PostInstallCommand,
    },
)