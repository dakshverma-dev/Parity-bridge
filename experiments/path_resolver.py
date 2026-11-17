"""Unrestricted filesystem path resolution for benchmark runs."""
import os

def resolve_run_path_unrestricted(path):
    return os.path.abspath(path)
