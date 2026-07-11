"""Create an uncompressed World of Tanks .wotmod package."""

from __future__ import print_function

import os
import sys
import zipfile


def main():
    if len(sys.argv) != 3:
        print("Usage: build_raw_py_wotmod.py PACKAGE_ROOT OUTPUT_WOTMOD")
        return 1

    package_root = os.path.abspath(sys.argv[1])
    output_path = os.path.abspath(sys.argv[2])

    if not os.path.isdir(package_root):
        print("Package root not found: {0}".format(package_root))
        return 1

    output_directory = os.path.dirname(output_path)
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for directory, _, filenames in os.walk(package_root):
            for filename in filenames:
                source_path = os.path.join(directory, filename)
                archive_path = os.path.relpath(source_path, package_root)
                archive.write(source_path, archive_path.replace(os.sep, "/"))

    print("Built {0}".format(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
