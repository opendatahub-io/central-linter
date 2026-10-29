#!/usr/bin/env python3

import os
import shutil
import sys
import importlib.resources


def copy_package_folder_to_destination(package_name, folder_name, destination_dir):
    package_folder = importlib.resources.files(package_name).joinpath(folder_name)

    os.makedirs(destination_dir, exist_ok=True)

    for entry in package_folder.iterdir():
        if entry.is_file():
            destination_path = os.path.join(destination_dir, entry.name)

            with entry.open('rb') as src_file:
                with open(destination_path, 'wb') as dst_file:
                    shutil.copyfileobj(src_file, dst_file)

            print(f"Copied {entry.name} to {destination_path}")
        
        elif entry.is_dir():
            new_destination_dir = os.path.join(destination_dir, entry.name)
            copy_package_folder_to_destination(package_name,
                                               os.path.join(folder_name, entry.name),
                                               new_destination_dir)


try:
    copy_package_folder_to_destination('lint', 'config', os.getcwd())
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
