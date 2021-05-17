#!/usr/bin/env python
"Make and extract deterministic zip archives."

import argparse
import hashlib
import os
import stat
import sys
from calendar import timegm
from subprocess import CalledProcessError, call
from time import gmtime, localtime, strftime
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


def _set_time(path, time):
    try:
        os.utime(path, (time, time))
    except OSError:
        pass
    if os.path.islink(path) and hasattr(os, "symlink"):
        try:
            os.utime(path, (time, time), follow_symlinks=False)
        except (NotImplementedError, TypeError, OSError):  # Windows, Python 2
            stamp = strftime("%Y%m%d%H%M.%S", localtime(time))
            try:
                call(["touch", "-h", "-t", stamp, path])
            except CalledProcessError:
                pass


def _extract_member(
    zf, member, extract_dir, time=None, preserve_symlinks=False
):
    extracted = zf.extract(member, extract_dir)
    attr = member.external_attr >> 16
    if attr:
        if stat.S_ISLNK(attr) and hasattr(os, "symlink") and preserve_symlinks:
            os.remove(extracted)
            os.symlink(zf.open(member).read(), extracted)
        else:
            os.chmod(extracted, attr)
    if time is not None:
        _set_time(extracted, time)
    else:
        _set_time(extracted, timegm(member.date_time + (0, 0, -1)))


def extract_zipfile(filename, extract_dir, time=None, preserve_symlinks=False):
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
            _extract_member(zf, member, extract_dir, time, preserve_symlinks)


def _get_files(base_dir, time=None):
    def get_mtime(path):
        if time is not None:
            return time
        return int(os.lstat(path).st_mtime)

    paths = [(base_dir + "/", get_mtime(base_dir))]
    for root, directories, files in os.walk(base_dir):
        for file in files:
            filepath = os.path.join(root, file)
            paths.append((filepath, get_mtime(filepath)))
        for directory in directories:
            dirpath = os.path.join(root, directory)
            if os.path.islink(dirpath):
                paths.append((dirpath, get_mtime(dirpath)))
            else:
                paths.append((dirpath + "/", get_mtime(dirpath)))
    return sorted(paths)


def _add_member(zf, path, mtime):
    zinfo = ZipInfo(path)
    zinfo.compress_type = ZIP_DEFLATED
    year, month, day, hour, minute, seconds, _, _, _ = gmtime(mtime)
    zinfo.date_time = (year, month, day, hour, minute, seconds)
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


def make_zipfile(base_name, base_dir, time=None):
    if time and (time < 315532800 or time > 4354819199):
        # 1980-01-01, 2107-12-31
        raise ValueError("Timestamp must be between 315532800 and 4354819199")
    with ZipFile(os.path.abspath(base_name), "w", allowZip64=True) as zf:
        for path, mtime in _get_files(base_dir, time):
            _add_member(zf, path, mtime)


def sha256sum(filepath):
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(4096), b""):
            hasher.update(block)
    return hasher.hexdigest()


def compare_digests(a, b):
    version = sys.version_info
    if (version.major, version.minor) >= (3, 6):
        from secrets import compare_digest

        return compare_digest(a, b)
    return a == b


def main(extract=False, desc=__doc__):
    parser = argparse.ArgumentParser(
        description=desc, usage="%(prog)s [options] <zipfile> <directory>"
    )
    parser.add_argument("zipfile", help="path to zipfile")
    parser.add_argument("directory", help="target directory")
    if not extract:
        parser.add_argument(
            "-x",
            "--extract",
            action="store_true",
            help="extract files from zipfile to directory",
        )
    parser.add_argument(
        "-s",
        "--preserve-symlinks",
        action="store_true",
        help="preserve/reconstruct symbolic links when extracting files",
    )
    parser.add_argument(
        "-t",
        "--time",
        action="store",
        metavar="time",
        type=int,
        help="override atime/mtime of files to given value (in unix seconds)",
    )
    parser.add_argument(
        "-p",
        "--print-digest",
        action="store_true",
        help="print sha256 hash digest of zipfile to stdout",
    )
    parser.add_argument(
        "-m",
        "--match-digest",
        action="store",
        metavar="digest",
        help="fail unless zipfile sha256 hash digest matches given value",
    )
    args = parser.parse_args()
    if extract:
        args.extract = True
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch and not args.time:  # Let "-t" flag override environment variable
        args.time = int(epoch)
    if not args.extract:
        try:
            make_zipfile(args.zipfile, args.directory, time=args.time)
        except Exception as exc:
            print("ERROR: {}".format(exc))
            return 1
    if args.print_digest or args.match_digest:
        digest = sha256sum(args.zipfile)
        if args.print_digest:
            print(digest)
        if args.match_digest:
            if not compare_digests(digest, args.match_digest):
                print(
                    "ERROR: SHA256 hash digest mismatch! "
                    "(expected: {}, received: {})".format(
                        args.match_digest, digest
                    )
                )
                return 1
    elif args.extract:
        try:
            extract_zipfile(
                args.zipfile,
                args.directory,
                time=args.time,
                preserve_symlinks=args.preserve_symlinks,
            )
        except Exception as exc:
            print("ERROR: {}".format(exc))
            return 1
    return 0


def dunzip():
    main(extract=True, desc="Extract deterministic zip archives.")


if __name__ == "__main__":
    sys.exit(main())
