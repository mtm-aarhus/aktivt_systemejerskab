"""The main file of the robot which will install all requirements in
a virtual environment and then start the actual process.
"""

import subprocess
import os
import sys

script_directory = os.path.dirname(os.path.realpath(__file__))
os.chdir(script_directory)

subprocess.run("python -m venv .venv", check=True)
subprocess.run([r'.venv\Scripts\python', '-m', 'pip', 'install', '--upgrade', 'pip'], check=True)
subprocess.run([r'.venv\Scripts\pip', 'install', '--only-binary=:all:', '-r', 'requirements.txt'], check=True)
subprocess.run([r'.venv\Scripts\pip', 'install', '--no-deps', '--no-build-isolation', '.'], check=True)

command_args = [r".venv\Scripts\python", "-m", "robot_framework"] + sys.argv[1:]

subprocess.run(command_args, check=True)
