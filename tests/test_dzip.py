import os
import stat
import sys
from io import BytesIO, StringIO
from subprocess import CalledProcessError, call
from time import localtime, strftime

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

import pytest

from dzip import __main__, create_zipfile, dunzip, extract_zipfile, main
from dzip.dzip import _get_args, _set_time, compare_digests, sha256sum


@pytest.fixture
def basedir(tmpdir):
    testdir = os.path.join(str(tmpdir), "Test")
    os.makedirs(testdir)

    subdir = os.path.join(testdir, "subdir")
    os.makedirs(subdir)

    file1 = os.path.join(testdir, "file1.txt")
    with open(file1, "w") as f:
        f.write("file1content")

    exefile = os.path.join(testdir, "test.exe")
    with open(exefile, "w") as f:
        f.write("test")
    st = os.stat(exefile)
    os.chmod(exefile, st.st_mode | stat.S_IEXEC)

    file2 = os.path.join(subdir, "file2.txt")
    with open(file2, "w") as f:
        f.write("file2content")

    file1link = os.path.join(testdir, "file1link")
    try:
        os.symlink("file1.txt", file1link)
    except (AttributeError, NotImplementedError):  # Windows
        pass

    subdirlink = os.path.join(testdir, "subdirlink")
    try:
        os.symlink("subdir", subdirlink)
    except (AttributeError, NotImplementedError):  # Windows
        pass

    # return str(tmpdir)

    time = 999999999
    os.utime(file2, (time, time))
    os.utime(subdir, (time, time))
    os.utime(file1, (time, time))
    os.utime(exefile, (time, time))
    os.utime(testdir, (time, time))
    if (sys.version_info.major, sys.version_info.minor) > (2, 7):
        try:
            os.utime(file1link, (time, time), follow_symlinks=False)
        except (AttributeError, NotImplementedError):  # Windows
            pass
        try:
            os.utime(subdirlink, (time, time), follow_symlinks=False)
        except (AttributeError, NotImplementedError):  # Windows
            pass
    else:  # Windows?
        stamp = strftime("%Y%m%d%H%M.%S", localtime(time))
        call(["touch", "-h", "-t", stamp, file1link])
        call(["touch", "-h", "-t", stamp, subdirlink])

    return str(tmpdir)


def test__set_time_pass_on_called_process_error(monkeypatch, basedir):
    monkeypatch.setattr("os.utime", Mock(side_effect=OSError))
    monkeypatch.setattr(
        "dzip.dzip.call",
        Mock(side_effect=CalledProcessError(returncode=1, cmd="touch")),
    )
    os.chdir(basedir)
    linkpath = os.path.join("Test", "file1link")
    _set_time(linkpath, 12345)
    assert int(os.lstat(linkpath).st_mtime) != 123456


def test_extract_zipfile(basedir):
    os.chdir(basedir)
    create_zipfile("Test.zip", "Test", time=1234567890)
    t = 444444444
    extract_zipfile("Test.zip", "output", time=t, preserve_symlinks=True)
    assert (
        int(os.lstat(os.path.join("output", "Test", "test.exe")).st_mtime) == t
    )


def test_create_zipfile_raise_value_error_timestamp_too_low(basedir):
    os.chdir(basedir)
    with pytest.raises(ValueError):
        create_zipfile("Test.zip", "Test", time=315532799)


def test_create_zipfile_raise_value_error_timestamp_too_high(basedir):
    os.chdir(basedir)
    with pytest.raises(ValueError):
        create_zipfile("Test.zip", "Test", time=4354819200)


def test_create_zipfile_is_deterministic(basedir):
    os.chdir(basedir)
    create_zipfile("1.zip", "Test")
    create_zipfile("2.zip", "Test")
    assert sha256sum("1.zip") == sha256sum("2.zip")


def test_create_zipfile_is_deterministic_with_time_override(basedir):
    os.chdir(basedir)
    create_zipfile("1.zip", "Test", time=1234567890)
    create_zipfile("2.zip", "Test", time=1234567890)
    assert sha256sum("1.zip") == sha256sum("2.zip")


def test_create_zipfile_is_deterministic_with_expected_digest(basedir):
    os.chdir(basedir)
    create_zipfile("Test.zip", "Test", time=1234567890)
    if sys.platform == "win32" and sys.version_info.major == 2:
        d = "c54792299242d3b46c6111e9b6a612dcb7a09105763d22e1bd434320ddc91ad6"
    elif sys.platform == "win32":
        d = "566f60f6841f69bac9e74fa051a1b9b304d1606403626b6fb5ea7ab7568e91f3"
    else:
        d = "b10992a74a98b63f00fba3e489c0dcd4bfbefc93884b7adb823f890649e08558"
    assert sha256sum("Test.zip") == d


def test_create_zipfile_output_changes_if_time_changes(basedir):
    os.chdir(basedir)
    create_zipfile("1.zip", "Test", time=1234567890)
    create_zipfile("2.zip", "Test", time=987654321)
    assert sha256sum("1.zip") != sha256sum("2.zip")


def test_compare_digests(basedir):
    os.chdir(basedir)
    create_zipfile("1.zip", "Test")
    create_zipfile("2.zip", "Test")
    assert compare_digests(sha256sum("1.zip"), sha256sum("2.zip")) is True


def test__get_args_extract_kwarg_default_is_false():
    args = _get_args(_args_list=["zipfile", "directory"])
    assert args.extract is False


def test__get_args_extract_kwarg_true():
    args = _get_args(extract=True, _args_list=["test.zip", "testdir"])
    assert args.extract is True


def test__get_args_read_source_date_epoch_environment_variable():
    env = os.environ
    env["SOURCE_DATE_EPOCH"] = str(999999999)
    args = _get_args(_args_list=["test.zip", "testdir"])
    del env["SOURCE_DATE_EPOCH"]
    assert args.time == 999999999


def test__get_args_t_flag_overrides_source_date_epoch_environement_variable():
    env = os.environ
    env["SOURCE_DATE_EPOCH"] = str(999999999)
    args = _get_args(_args_list=["-t", "123454321", "test.zip", "testdir"])
    del env["SOURCE_DATE_EPOCH"]
    assert args.time == 123454321


def test_main_create_zipfile(basedir):
    os.chdir(basedir)
    main(_args=_get_args(_args_list=["TestMainCreate.zip", "Test"]))
    assert os.path.exists("TestMainCreate.zip") is True


def test_main_use_real_args(monkeypatch, basedir):
    monkeypatch.setattr("sys.stderr", Mock())
    monkeypatch.setattr("sys.exit", Mock())
    retcode = main()
    assert retcode == 1


def test_main_create_zipfile_return_1_on_error(monkeypatch, basedir):
    monkeypatch.setattr("sys.stderr", Mock())
    monkeypatch.setattr(
        "dzip.dzip.create_zipfile", Mock(side_effect=ValueError)
    )
    os.chdir(basedir)
    rc = main(_args=_get_args(_args_list=["TestMainCreate.zip", "Test"]))
    assert rc == 1


def test_main_extract_zipfile_return_1_on_error(monkeypatch, basedir):
    monkeypatch.setattr("sys.stderr", Mock())
    monkeypatch.setattr(
        "dzip.dzip.extract_zipfile", Mock(side_effect=ValueError)
    )
    os.chdir(basedir)
    rc = main(_args=_get_args(_args_list=["-x", "TestMainCreate.zip", "Test"]))
    assert rc == 1


def test_main_extract_zipfile_into_existing_directory(monkeypatch, basedir):
    os.chdir(basedir)
    create_zipfile("Test.zip", "Test", time=888888888)
    main(_args=_get_args(_args_list=["-x", "Test.zip", "."]))
    assert (
        int(os.lstat(os.path.join("Test", "test.exe")).st_mtime) == 888888888
    )


def test_main_create_print_digest(monkeypatch, basedir):
    if sys.version_info.major == 2:
        buffer = BytesIO()
    else:
        buffer = StringIO()
    monkeypatch.setattr("sys.stdout", buffer)
    os.chdir(basedir)
    a = ["-p", "-t", "1234567890", "TestMainCreate.zip", "Test"]
    main(_args=_get_args(_args_list=a))
    printed_digest = buffer.getvalue().strip()
    if sys.platform == "win32" and sys.version_info.major == 2:
        d = "c54792299242d3b46c6111e9b6a612dcb7a09105763d22e1bd434320ddc91ad6"
    elif sys.platform == "win32":
        d = "566f60f6841f69bac9e74fa051a1b9b304d1606403626b6fb5ea7ab7568e91f3"
    else:
        d = "b10992a74a98b63f00fba3e489c0dcd4bfbefc93884b7adb823f890649e08558"
    assert printed_digest == d


def test_main_create_match_digest(monkeypatch, basedir):
    monkeypatch.setattr("sys.stderr", Mock())
    os.chdir(basedir)
    m = "0000000000000000000000000000000000000000000000000000000000000001"
    retcode = main(_args=_get_args(_args_list=["-m", m, "Test.zip", "Test"]))
    assert retcode == 1


def test_dunzip_extract(monkeypatch, basedir):
    monkeypatch.setattr("sys.exit", Mock())
    os.chdir(basedir)
    create_zipfile("Test.zip", "Test")
    args = _get_args(extract=True, _args_list=["Test.zip", "DunzipDirectory"])
    dunzip(_args=args)
    assert os.path.exists("DunzipDirectory")
