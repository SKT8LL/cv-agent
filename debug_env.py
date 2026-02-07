import sys
import os

print(f"User: {os.environ.get('USER')}")
print(f"Python Executable: {sys.executable}")
print(f"Prefix: {sys.prefix}")
