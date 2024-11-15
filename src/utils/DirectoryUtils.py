import inspect
import os

def find_folder(func):
    split_module_path = split_path(inspect.getfile(func))
    # assumes last element is the file's name
    return os.path.abspath("/".join(split_module_path[:-1]))

def split_path(path):
    # clean up slashes, windows likes back linux likes forward. want to deal with either case
    temp_path = path.replace("\\", "/")
    split_path = [temp_path]
    if temp_path.find("/") >= 0:
        # file is nested in some directories, need to separate everything out to isolate file name
        split_path = temp_path.split("/")
    return split_path
