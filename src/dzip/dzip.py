#!/usr/bin/env python
"Make and extract deterministic zip archives."

import argparse
import hashlib
import os
import stat
import sys
from subprocess import call
from time import localtime, mktime
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def _set_time(path, date_time):
    time = mktime(date_time + (0, 0, -1))
    try:
        os.utime(path, (time, time))
    except OSError:
        pass
    if os.path.islink(path) and hasattr(os, "symlink"):
        try:
            os.utime(path, (time, time), follow_symlinks=False)
        except (NotImplementedError, TypeError, OSError):  # Windows, Python 2
            try:
                # On both GNU/Linux and BSD/darwin, the "-r" flag reads
                # and uses the access and modification times of the
                # specified file (instead of the current local system
                # time), while the "-h" (or "--no-dereference") flag
                # applies the change to the symlink itself (instead of
                # to its target). Taken together, this sets the 
                # symlink's atime/mtime to that of its target.
                call(["touch", "-r", path, "-h", path])
            except:
                pass


def extract_zipfile(filename, extract_dir, date_time=None):
    try:
        os.makedirs(extract_dir)
    except OSError:
        pass
    with ZipFile(filename) as zf:
        # Iterate through the files-list backwards so that files that
        # are deeper in the directory hierarchy get extracted first.
        # This facilitates setting the timestamps for higher-level
        # directories *after* the dirs/files within them have been
        # extracted (and thereby prevents them from being overridden).
        for member in reversed(zf.infolist()):
            extracted = zf.extract(member, extract_dir)
            attr = member.external_attr >> 16
            if attr:
                if stat.S_ISLNK(attr) and hasattr(os, "symlink"):
                    os.remove(extracted)
                    os.symlink(zf.open(member).read(), extracted)
                else:
                    os.chmod(extracted, attr)
            if not date_time:
                date_time = member.date_time
            if date_time:
                _set_time(extracted, date_time)


def make_zipfile(base_name, base_dir, date_time=(2021, 1, 1, 0, 0, 0)):
    paths = [base_dir + "/"]
    for root, directories, files in os.walk(base_dir):
        for file in files:
            paths.append(os.path.join(root, file))
        for directory in directories:
            dirpath = os.path.join(root, directory)
            if os.path.islink(dirpath):
                paths.append(dirpath)
            else:
                paths.append(dirpath + "/")
    with ZipFile(os.path.abspath(base_name), "w", ZIP_DEFLATED) as zf:
        for path in sorted(paths):
            zinfo = ZipInfo(path)
            zinfo.date_time = date_time
            if path.endswith("/"):
                zinfo.external_attr = (0o755 | stat.S_IFDIR) << 16
                zf.writestr(zinfo, "")
            elif os.path.islink(path):
                zinfo.filename = path  # To strip trailing "/" from dirs
                zinfo.external_attr = (0o755 | stat.S_IFLNK) << 16
                zf.writestr(zinfo, os.readlink(path))
            else:
                if os.access(path, os.X_OK):
                    zinfo.external_attr = (0o755 | stat.S_IFREG) << 16
                else:
                    zinfo.external_attr = (0o644 | stat.S_IFREG) << 16
                with open(path, "rb") as f:
                    zf.writestr(zinfo, f.read())



def sha256sum(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, usage="%(prog)s [options] <zipfile> <directory>"
    )
    parser.add_argument("zipfile", help="path to zipfile")
    parser.add_argument("directory", help="target directory")
    parser.add_argument(
        "-x", "--extract",
        action="store_true",
        help="extract files from zipfile to directory"
    )
    parser.add_argument(
        "-t", "--time",
        action="store",
        metavar="time",
        type=int,
        help="override atime/mtime of files to given value (in unix seconds)"
    )
    parser.add_argument(
        "-p", "--print-digest",
        action="store_true",
        help="print sha256 hash digest of zipfile to stdout"
    )
    parser.add_argument(
        "-m", "--match-digest",
        action="store",
        metavar="digest",
        help="fail unless zipfile sha256 hash digest matches given value"
    )

    args = parser.parse_args()
    if args.time:
        year, month, day, hour, minute, second, _, _, _ = localtime(args.time)
        date_time = (year, month, day, hour, minute, second)
        if args.extract:
            extract_zipfile(args.zipfile, args.directory, date_time)
        else:
            make_zipfile(args.zipfile, args.directory, date_time)
    elif args.extract:
        extract_zipfile(args.zipfile, args.directory)
    else:
        make_zipfile(args.zipfile, args.directory)
    if args.print_digest or args.match_digest:
        digest = sha256sum(args.zipfile)
        if args.print_digest:
            print(digest)
        if args.match_digest and args.match_digest != digest:
            print(
                "ERROR: SHA256 hash digest mismatch! "
                "(expected: {}, received: {})".format(
                    args.match_digest, digest
                )
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
