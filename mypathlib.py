# Commit: https://github.com/python/cpython/commit/0185f34ddcf07b78feb6ac666fbfd4615d26b028#diff-ab57fbd24b8af25b7267289a32704048

import fnmatch
import io
import os
from pathlib import _PathParents
from stat import S_ISDIR, S_ISLNK, S_ISREG, S_ISSOCK, S_ISBLK, S_ISCHR, S_ISFIFO

from icontract import pre, post

supports_symlinks = True


class PurePosixPath:
    pass


class PurePath(object):
    """Base class for manipulating paths without I/O.

    PurePath represents a filesystem path and offers operations which
    don't imply any actual filesystem I/O.  Depending on your system,
    instantiating a PurePath will return either a PurePosixPath or a
    PureWindowsPath object.  You can also instantiate either of these classes
    directly, regardless of your system.
    """

    @pre(lambda args, result: not (not args) or not result.parts)
    @pre(lambda args, result: not (not args) or str(result) == '.',
         "When pathsegments is empty, the current directory is assumed")
    @pre(lambda args, result: not any(Path(arg).is_absolute() for arg in args) or
                              (result == [pth for arg in args for pth in [Path(arg)] if pth.is_absolute()][-1]),
         "When several absolute paths are given, the last is taken as an anchor (mimicking os.path.join()’s behaviour)")
    @post(lambda result: '//' not in str(result), "Spurious slashes are collapsed")
    @post(lambda result: '/./' not in str(result), "Spurious dots are collapsed")
    @post(lambda args, result: not any('..' in arg for arg in args) or '..' in str(result),
          "Double dots are not collapsed, since this would change the meaning of a path in the face of symbolic links")
    def __new__(cls, *args):
        """Construct a PurePath from one or several strings and or existing
        PurePath objects.  The strings and path objects are combined so as
        to yield a canonicalized path, which is incorporated into the
        new PurePath object.
        """
        if cls is PurePath:
            cls = PureWindowsPath if os.name == 'nt' else PurePosixPath

        return cls._from_parts(args)

    @pre(lambda self: all(len(part) < 256 for part in self.parts), "Contains no path components longer than 255 bytes")
    @post(lambda result: '\x00' not in result, "Contains no null-byte")
    @post(lambda self, result: not (not self.parts) or result == '.', "Empty path is '.'")
    def as_posix(self):
        """Return the string representation of the path with forward (/)
        slashes.

        :return: something
        """
        f = self._flavour
        return str(self).replace(f.sep, '/')

    @pre(lambda self: self.is_absolute(), "relative path can't be expressed as a file URI.")
    @post(lambda self, result: result == "file://" + self.as_posix())
    @post(lambda result: False,
          "??? Can it have an URL fragment? Can it have queries? Is it URL-encoded or needs to be URL-encoded by the caller?")
    def as_uri(self):
        """Return the path as a 'file' URI."""
        if not self.is_absolute():
            raise ValueError("relative path can't be expressed as a file URI")
        return self._flavour.make_uri(self)

    @property
    @post(lambda self, result: not (not self.is_absolute()) or result == "", "Drive of relative paths is empty.")
    @post(lambda self, result: not (isinstance(self, PosixPath)) or result == "", "Linux paths have no drives.")
    def drive(self):
        """The drive prefix (letter or UNC path), if any."""
        return self._drv

    @property
    @post(lambda self, result: not (not self.is_absolute()) or result == "", "Root of relative paths is empty.")
    def root(self):
        """The root of the path, if any."""
        return self._root

    @property
    @post(lambda self, result: not self.is_absolute() or result == self.drive + self.root,
          "The concatenation of the drive and root.")
    @post(lambda self, result: not (not self.is_absolute()) or result == '', "No anchor in relative paths.")
    def anchor(self):
        """The concatenation of the drive and root, or ''."""
        anchor = self._drv + self._root
        return anchor

    @property
    @post(lambda result: os.path.sep not in result)
    @post(lambda self, result: not (self == Path(self.anchor)) or result == "")
    @post(lambda self, result: not (self != Path(self.anchor)) or result == self.parts[-1])
    def name(self):
        """The final path component, if any."""
        parts = self._parts
        if len(parts) == (1 if (self._drv or self._root) else 0):
            return ''
        return parts[-1]

    @property
    @post(lambda result: result == "" or result.startswith("."))
    @post(lambda self, result: self.name() or result == "")
    @post(lambda self, result: self.name().endswith(result))
    @post(lambda self, result: self.name() == self.stem() + result)
    @post(lambda self, result: not self.name().endswith(".") or result == "")
    @post(lambda self, result: not ("." in self.name()[:-1]) or result != "")
    def suffix(self):
        """The final component's last suffix, if any."""
        name = self.name
        i = name.rfind('.')
        if 0 < i < len(name) - 1:
            return name[i:]
        else:
            return ''

    @property
    @post(lambda result: all(item.startswith(".") for item in result))
    @post(lambda result: all(not item.endswith(".") for item in result))
    @post(lambda self, result: self.name() or result == [])
    @post(lambda self, result: self.name().endswith(".") or self.suffix() == "".join(result))
    @post(lambda self, result: not self.name().endswith(".") or result == [])
    @post(lambda self, result: result == [] or self.name() == self.stem + result[-1])
    def suffixes(self):
        """A list of the final component's suffixes, if any."""
        name = self.name
        if name.endswith('.'):
            return []
        name = name.lstrip('.')
        return ['.' + suffix for suffix in name.split('.')[1:]]

    @property
    @post(lambda self, result: self.name() == result + self.suffix())
    @post(lambda self, result: not (self.name().endswith(".")) or result == self.name())
    def stem(self):
        """The final path component, minus its last suffix."""
        name = self.name
        i = name.rfind('.')
        if 0 < i < len(name) - 1:
            return name[:i]
        else:
            return name

    @pre(lambda self: self.name, "The original path must have a name.")
    @post(lambda self, name, result: result.name() == name)
    @post(lambda self, result: result.parent == self.parent)
    def with_name(self, name):
        """Return a new path with the file name changed."""
        if not self.name:
            raise ValueError("%r has an empty name" % (self,))
        drv, root, parts = self._flavour.parse_parts((name,))
        if (not name or name[-1] in [self._flavour.sep, self._flavour.altsep]
                or drv or root or len(parts) != 1):
            raise ValueError("Invalid name %r" % (name))
        return self._from_parsed_parts(self._drv, self._root,
                                       self._parts[:-1] + [name])

    @pre(lambda suffix: not os.path.sep in suffix)
    @pre(lambda suffix: not os.path.altsep in suffix)
    @pre(lambda suffix: suffix.startswith("."))
    @pre(lambda suffix: suffix and suffix != '.')
    @pre(lambda self: self.name(), "The original path must have a name.")
    @post(lambda self, result: result.parent == self.parent)
    @post(lambda self, suffix, result: not (not self.suffix) or (result.name == self.name + suffix),
          "If the original path doesn’t have a suffix, the new suffix is appended instead.")
    @post(lambda self, suffix, result: not (not suffix) or (not result.suffix),
          "If the suffix is an empty string, the original suffix is removed.")
    def with_suffix(self, suffix):
        """Return a new path with the file suffix changed.  If the path
        has no suffix, add given suffix.  If the given suffix is an empty
        string, remove the suffix from the path.
        """
        f = self._flavour
        if f.sep in suffix or f.altsep and f.altsep in suffix:
            raise ValueError("Invalid suffix %r" % (suffix,))
        if suffix and not suffix.startswith('.') or suffix == '.':
            raise ValueError("Invalid suffix %r" % (suffix))
        name = self.name
        if not name:
            raise ValueError("%r has an empty name" % (self,))
        old_suffix = self.suffix
        if not old_suffix:
            name = name + suffix
        else:
            name = name[:-len(old_suffix)] + suffix
        return self._from_parsed_parts(self._drv, self._root,
                                       self._parts[:-1] + [name])

    def relative_to(self, *other):
        """Return the relative path to another path identified by the passed
        arguments.  If the operation is not possible (because this is not
        a subpath of the other path), raise ValueError.
        """
        # For the purpose of this method, drive and root are considered
        # separate parts, i.e.:
        #   Path('c:/').relative_to('c:')  gives Path('/')
        #   Path('c:/').relative_to('/')   raise ValueError
        if not other:
            raise TypeError("need at least one argument")
        parts = self._parts
        drv = self._drv
        root = self._root
        if root:
            abs_parts = [drv, root] + parts[1:]
        else:
            abs_parts = parts
        to_drv, to_root, to_parts = self._parse_args(other)
        if to_root:
            to_abs_parts = [to_drv, to_root] + to_parts[1:]
        else:
            to_abs_parts = to_parts
        n = len(to_abs_parts)
        cf = self._flavour.casefold_parts
        if (root or drv) if n == 0 else cf(abs_parts[:n]) != cf(to_abs_parts):
            formatted = self._format_parsed_parts(to_drv, to_root, to_parts)
            raise ValueError("{!r} does not start with {!r}"
                             .format(str(self), str(formatted)))
        return self._from_parsed_parts('', root if n == 1 else '',
                                       abs_parts[n:])

    @property
    @post(lambda self, result: not self.is_absolute() or len(result) >= 1)
    @post(lambda self, result: not self.is_absolute() or result[0] == self.anchor,
          "The anchor is regrouped in a single part")
    @post(lambda self, result: not isinstance(self, PurePosixPath) or os.path.sep.join(result) == str(self))
    def parts(self):
        """An object providing sequence-like access to the
        components in the filesystem path."""
        # We cache the tuple to avoid building a new one each time .parts
        # is accessed.  XXX is this necessary?
        try:
            return self._pparts
        except AttributeError:
            self._pparts = tuple(self._parts)
            return self._pparts

    @post(lambda self: False, "??? I am not familiar with this function enough.")
    def joinpath(self, *args):
        """XXXCombine this path with one or several arguments, and return a
        new path representing either a subpath (if all arguments are relative
        paths) or a totally different path (if one of the arguments is
        anchored).
        """
        return self._make_child(args)

    @post(lambda self, key, result: not (not Path(key).is_absolute()) or self in result.parents)
    @post(lambda self, key, result: not (not Path(key).is_absolute()) or result.relative_to(self) == Path(key))
    @post(lambda key, result: not Path(key).is_absolute() or result == Path(key))
    def __truediv__(self, key):
        """MR: dummy truediv doc so that it displays in sphinx."""
        return self._make_child((key,))

    def __rtruediv__(self, key):
        return self._from_parts([key] + self._parts)

    @property
    @post(lambda self, result: not (not self.parts) or result == self, "You can not go past an empty path")
    @post(lambda self, result: not (len(self.parts) == 1 and self.is_absolute()) or result == self,
          "You can not go past an anchor")
    @post(lambda self, result: not (len(self.parts) > 1) or result.name == self.parts[-2],
          "This is purely lexical operation.")
    def parent(self):
        """The logical parent of the path."""
        drv = self._drv
        root = self._root
        parts = self._parts
        if len(parts) == 1 and (drv or root):
            return self
        return self._from_parsed_parts(drv, root, parts[:-1])

    @property
    @post(lambda self, result: not (self.parent == self) or not result)
    @post(lambda self, result: not (self.parent != self) or self.parent == result[-1])
    @post(lambda self, result: not (self.parent != self) or all(p1.parent == p2 for p1, p2 in pairwise(result)))
    def parents(self):
        """A sequence of this path's logical parents."""
        return _PathParents(self)

    @post(lambda self, result: not result or self.root != "", "Absolute paths have non-empty root")
    def is_absolute(self):
        """True if the path is absolute (has both a root and, if applicable,
        a drive)."""
        if not self._root:
            return False
        return not self._flavour.has_drv or bool(self._drv)

    @post(lambda self, result: not isinstance(self, PurePosixPath) or not result,
          "With PurePosixPath, False is always returned.")
    def is_reserved(self):
        """Return True if the path contains one of the special names reserved
        by the system, if any."""
        return self._flavour.is_reserved(self._parts)

    @pre(lambda self, path_pattern: not (not self.is_absolute()) or True,
         "If pattern is relative, the path can be either relative or absolute.")
    @pre(lambda self, path_pattern: not self.is_absolute() or Path(path_pattern).is_absolute(),
         "If pattern is absolute, the path must be absolute.")
    def match(self, path_pattern):
        """
        Return True if this path matches the given pattern.
        """
        cf = self._flavour.casefold
        path_pattern = cf(path_pattern)
        drv, root, pat_parts = self._flavour.parse_parts((path_pattern,))
        if not pat_parts:
            raise ValueError("empty pattern")
        if drv and drv != cf(self._drv):
            return False
        if root and root != cf(self._root):
            return False
        parts = self._cparts
        if drv or root:
            if len(pat_parts) != len(parts):
                return False
            pat_parts = pat_parts[1:]
        elif len(pat_parts) > len(parts):
            return False
        for part, pat in zip(reversed(parts), reversed(pat_parts)):
            if not fnmatch.fnmatchcase(part, pat):
                return False
        return True


class PurePosixPath(PurePath):
    """PurePath subclass for non-Windows systems.

    On a POSIX system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    pass


class PureWindowsPath(PurePath):
    """PurePath subclass for Windows systems.

    On a Windows system, instantiating a PurePath should return this object.
    However, you can also instantiate it directly on any system.
    """
    pass


class Path(PurePath):
    """PurePath subclass that can make system calls.

    Path represents a filesystem path but unlike PurePath, also offers
    methods to do system calls on path objects. Depending on your system,
    instantiating a Path will return either a PosixPath or a WindowsPath
    object. You can also instantiate a PosixPath or WindowsPath directly,
    but cannot instantiate a WindowsPath on a POSIX system or vice versa.
    """

    # Public API

    @classmethod
    @post(lambda result: result == os.getcwd())
    def cwd(cls):
        """Return a new path pointing to the current working directory
        (as returned by os.getcwd()).
        """
        return cls(os.getcwd())

    @classmethod
    @post(lambda result: result == os.path.expanduser('~'))
    def home(cls):
        """Return a new path pointing to the user's home directory (as
        returned by os.path.expanduser('~')).
        """
        return cls(cls()._flavour.gethomedir(None))

    @pre(lambda other_path: isinstance(other_path, (str, Path)), "other_path can be either a Path object, or a string")
    @post(lambda self, other_path, result: result == os.path.samefile(str(self), str(other_path)),
          "The semantics are similar to os.path.samefile() and os.path.samestat() ??? "
          "I don't understand what is meant here with semantics similar to os.path.samestat().")
    def samefile(self, other_path):
        """Return whether other_path is the same or not as this file
        (as returned by os.path.samefile()).
        """
        st = self.stat()
        try:
            other_st = other_path.stat()
        except AttributeError:
            other_st = os.stat(other_path)
        return os.path.samestat(st, other_st)

    def iterdir(self):
        """Iterate over the files in this directory.  Does not yield any
        result for the special paths '.' and '..'.
        """
        if self._closed:
            self._raise_closed()
        for name in self._accessor.listdir(self):
            if name in {'.', '..'}:
                # Yielding a path object for these makes little sense
                continue
            yield self._make_child_relpath(name)
            if self._closed:
                self._raise_closed()

    @pre(lambda pattern: pattern, "Unacceptable pattern")
    @pre(lambda pattern: not Path(pattern).is_absolute(), "Non-relative patterns are unsupported")
    def glob(self, pattern):
        """Iterate over this subtree and yield all existing files (of any
        kind, including directories) matching the given pattern.
        """
        if not pattern:
            raise ValueError("Unacceptable pattern: {!r}".format(pattern))
        pattern = self._flavour.casefold(pattern)
        drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        if drv or root:
            raise NotImplementedError("Non-relative patterns are unsupported")
        selector = _make_selector(tuple(pattern_parts))
        for p in selector.select_from(self):
            yield p

    @pre(lambda pattern: pattern, "Unacceptable pattern")
    @pre(lambda pattern: not Path(pattern).is_absolute(), "Non-relative patterns are unsupported")
    def rglob(self, pattern):
        """Recursively yield all existing files (of any kind, including
        directories) matching the given pattern, anywhere in this subtree.
        """
        pattern = self._flavour.casefold(pattern)
        drv, root, pattern_parts = self._flavour.parse_parts((pattern,))
        if drv or root:
            raise NotImplementedError("Non-relative patterns are unsupported")
        selector = _make_selector(("**",) + tuple(pattern_parts))
        for p in selector.select_from(self):
            yield p

    @post(lambda self, result: not self.is_absolute() or self == result)
    @post(lambda self, result: not ('.' in self.parts) or '.' in result.parts)
    @post(lambda self, result: not ('..' in self.parts) or '..' in result.parts)
    @post(lambda result: result.is_absolute())
    def absolute(self):
        """Return an absolute version of this path.  This function works
        even if the path doesn't point to anything.

        No normalization is done, i.e. all '.' and '..' will be kept along.
        Use resolve() to get the canonical path to a file.
        """
        # XXX untested yet!
        if self._closed:
            self._raise_closed()
        if self.is_absolute():
            return self
        # FIXME this must defer to the specific flavour (and, under Windows,
        # use nt._getfullpathname())
        obj = self._from_parts([os.getcwd()] + self._parts, init=False)
        obj._init(template=self)
        return obj

    @pre(lambda self, strict: not strict or self.exists())
    @pre(lambda self, strict: not (not strict) or True,
         "The path is resolved as far as possible and any remainder is appended without checking whether it exists. "
         "If an infinite loop is encountered along the resolution path, RuntimeError is raised.")
    @post(lambda result: result.is_absolute())
    @post(lambda result: '..' not in result.parts, "``..`` components are eliminated.")
    def resolve(self, strict=False):
        """
        Make the path absolute, resolving all symlinks on the way and also
        normalizing it (for example turning slashes into backslashes under
        Windows).
        """
        if self._closed:
            self._raise_closed()
        s = self._flavour.resolve(self, strict=strict)
        if s is None:
            # No symlink resolution => for consistency, raise an error if
            # the path doesn't exist or is forbidden
            self.stat()
            s = str(self.absolute())
        # Now we have no symlinks in the path, it's safe to normalize it.
        normed = self._flavour.pathmod.normpath(s)
        obj = self._from_parts((normed,), init=False)
        obj._init(template=self)
        return obj

    @post(lambda self, result: not (result is not None) or
                               os.stat(str(self)).__dict__ == result.__dict__,
          "??? This is probably not what it was meant with 'like os.stat() does'?")
    @post(lambda self, result: not (result is not None) or self.exists())
    def stat(self):
        """
        Return the result of the stat() system call on this path, like
        os.stat() does.
        """
        return self._accessor.stat(self)

    def owner(self):
        """
        Return the login name of the file owner.
        """
        import pwd
        return pwd.getpwuid(self.stat().st_uid).pw_name

    def group(self):
        """
        Return the group name of the file gid.
        """
        import grp
        return grp.getgrgid(self.stat().st_gid).gr_name

    def open(self, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None):
        """
        Open the file pointed by this path and return a file object, as
        the built-in open() function does.
        """
        if self._closed:
            self._raise_closed()
        return io.open(self, mode, buffering, encoding, errors, newline,
                       opener=self._opener)

    def read_bytes(self):
        """
        Open the file in bytes mode, read it, and close the file.
        """
        with self.open(mode='rb') as f:
            return f.read()

    def read_text(self, encoding=None, errors=None):
        """
        Open the file in text mode, read it, and close the file.
        """
        with self.open(mode='r', encoding=encoding, errors=errors) as f:
            return f.read()

    def write_bytes(self, data):
        """
        Open the file in bytes mode, write to it, and close the file.
        """
        # type-check for the buffer interface before truncating the file
        view = memoryview(data)
        with self.open(mode='wb') as f:
            return f.write(view)

    @pre(lambda data: isinstance(data, str), 'data must be str')
    def write_text(self, data, encoding=None, errors=None):
        """
        Open the file in text mode, write to it, and close the file.
        """
        if not isinstance(data, str):
            raise TypeError('data must be str, not %s' %
                            data.__class__.__name__)
        with self.open(mode='w', encoding=encoding, errors=errors) as f:
            return f.write(data)

    @pre(lambda self, exist_ok: not self.exists or exist_ok,
         "If the file already exists, the function succeeds if exist_ok is true.")
    def touch(self, mode=0o666, exist_ok=True):
        """
        Create this file with the given access mode, if it doesn't exist.
        """
        if self._closed:
            self._raise_closed()
        if exist_ok:
            # First try to bump modification time
            # Implementation note: GNU touch uses the UTIME_NOW option of
            # the utimensat() / futimens() functions.
            try:
                self._accessor.utime(self, None)
            except OSError:
                # Avoid exception chaining
                pass
            else:
                return
        flags = os.O_CREAT | os.O_WRONLY
        if not exist_ok:
            flags |= os.O_EXCL
        fd = self._raw_open(flags, mode)
        os.close(fd)

    @pre(lambda self, exist_ok: not (self.exists()) or exist_ok)
    @pre(lambda self, parents: not (not self.parent.exists()) or parents)
    def mkdir(self, mode=0o777, parents=False, exist_ok=False):
        """
        Create a new directory at this given path.
        """
        if self._closed:
            self._raise_closed()
        try:
            self._accessor.mkdir(self, mode)
        except FileNotFoundError:
            if not parents or self.parent == self:
                raise
            self.parent.mkdir(parents=True, exist_ok=True)
            self.mkdir(mode, parents=False, exist_ok=exist_ok)
        except OSError:
            # Cannot rely on checking for EEXIST, since the operating system
            # could give priority to other errors like EACCES or EROFS
            if not exist_ok or not self.is_dir():
                raise

    @post(lambda: True, "??? It would make sense to use old(self.stat()) and compare it against the new mode.")
    def chmod(self, mode):
        """
        Change the permissions of the path, like os.chmod().
        """
        if self._closed:
            self._raise_closed()
        self._accessor.chmod(self, mode)

    @post(lambda: True, "??? It would make sense to use old(self.stat()) and compare it against the new mode. "
                        "This would need a case distinction for symlink yes/no.")
    def lchmod(self, mode):
        """
        Like chmod(), except if the path points to a symlink, the symlink's
        permissions are changed, rather than its target's.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.lchmod(self, mode)

    @pre(lambda self: self.is_file(), "The path points to a directory, use Path.rmdir() instead.")
    def unlink(self):
        """
        Remove this file or link.
        If the path is a directory, use rmdir() instead.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.unlink(self)

    @pre(lambda self: self.is_dir())
    @pre(lambda self: not list(self.iterdir()), "??? There must be a way to check this more optimally")
    def rmdir(self):
        """
        Remove this directory.  The directory must be empty.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.rmdir(self)

    @post(lambda self, result: not (result and self.is_symlink()) or result.__dict__ == self.resolve().stat(),
          "If the path points to a symbolic link, return the symbolic link’s information rather than its target’s.")
    @post(lambda self, result: not (result and not self.is_symlink()) or result.__dict__ == self.stat(),
          "Same as Path.stat()")
    def lstat(self):
        """
        Like stat(), except if the path points to a symlink, the symlink's
        status information is returned, rather than its target's.
        """
        if self._closed:
            self._raise_closed()
        return self._accessor.lstat(self)

    def rename(self, target):
        """
        Rename this path to the given path.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.rename(self, target)

    def replace(self, target):
        """
        Rename this path to the given path, clobbering the existing
        destination if it exists.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.replace(self, target)

    @pre(lambda self, target, target_is_directory:
         not (isinstance(self, PureWindowsPath) and target.is_dir()) or target_is_directory == True,
         "Under Windows, target_is_directory must be true (default False) if the link’s target is a directory.")
    def symlink_to(self, target, target_is_directory=False):
        """
        Make this path a symlink pointing to the given path.
        Note the order of arguments (self, target) is the reverse of os.symlink's.
        """
        if self._closed:
            self._raise_closed()
        self._accessor.symlink(target, self, target_is_directory)

    # Convenience functions for querying the stat results

    @post(lambda self, result: not self.is_symlink() or (result == self.resolve().exists()),
          "If the path points to a symlink, exists() returns whether the symlink points to an existing "
          "file or directory.")
    def exists(self):
        """
        Whether this path exists.
        """
        try:
            self.stat()
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            return False
        except ValueError:
            # Non-encodable path
            return False
        return True

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist. "
                                                                      "??? How do we check if it's a broken symlink?")
    def is_dir(self):
        """
        Whether this path is a directory.
        """
        try:
            return S_ISDIR(self.stat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist or is a broken symlink
            # (see https://bitbucket.org/pitrou/pathlib/issue/12/)
            return False
        except ValueError:
            # Non-encodable path
            return False

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist."
                                                                      "??? How do we check if it's a broken symlink?")
    def is_file(self):
        """
        Whether this path is a regular file (also True for symlinks pointing
        to regular files).
        """
        try:
            return S_ISREG(self.stat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist or is a broken symlink
            # (see https://bitbucket.org/pitrou/pathlib/issue/12/)
            return False
        except ValueError:
            # Non-encodable path
            return False

    def is_mount(self):
        """
        Check if this path is a POSIX mount point
        """
        # Need to exist and be a dir
        if not self.exists() or not self.is_dir():
            return False

        parent = Path(self.parent)
        try:
            parent_dev = parent.stat().st_dev
        except OSError:
            return False

        dev = self.stat().st_dev
        if dev != parent_dev:
            return True
        ino = self.stat().st_ino
        parent_ino = parent.stat().st_ino
        return ino == parent_ino

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist.")
    def is_symlink(self):
        """
        Whether this path is a symbolic link.
        """
        try:
            return S_ISLNK(self.lstat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist
            return False
        except ValueError:
            # Non-encodable path
            return False

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist.")
    def is_block_device(self):
        """
        Whether this path is a block device.
        """
        try:
            return S_ISBLK(self.stat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist or is a broken symlink
            # (see https://bitbucket.org/pitrou/pathlib/issue/12/)
            return False
        except ValueError:
            # Non-encodable path
            return False

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist.")
    def is_char_device(self):
        """
        Whether this path is a character device.
        """
        try:
            return S_ISCHR(self.stat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist or is a broken symlink
            # (see https://bitbucket.org/pitrou/pathlib/issue/12/)
            return False
        except ValueError:
            # Non-encodable path
            return False

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist.")
    def is_fifo(self):
        """
        Whether this path is a FIFO.
        """
        try:
            return S_ISFIFO(self.stat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist or is a broken symlink
            # (see https://bitbucket.org/pitrou/pathlib/issue/12/)
            return False
        except ValueError:
            # Non-encodable path
            return False

    @post(lambda self, result: not (not self.exists()) or not result, "False is returned if the path doesn’t exist.")
    def is_socket(self):
        """
        Whether this path is a socket.
        """
        try:
            return S_ISSOCK(self.stat().st_mode)
        except OSError as e:
            if e.errno not in _IGNORED_ERROS:
                raise
            # Path doesn't exist or is a broken symlink
            # (see https://bitbucket.org/pitrou/pathlib/issue/12/)
            return False
        except ValueError:
            # Non-encodable path
            return False

    def expanduser(self):
        """ Return a new path with expanded ~ and ~user constructs
        (as returned by os.path.expanduser)
        """
        if (not (self._drv or self._root) and
                self._parts and self._parts[0][:1] == '~'):
            homedir = self._flavour.gethomedir(self._parts[0][1:])
            return self._from_parts([homedir] + self._parts[1:])

        return self


class PosixPath(Path, PurePosixPath):
    """Path subclass for non-Windows systems.

    On a POSIX system, instantiating a Path should return this object.
    """
    __slots__ = ()


class WindowsPath(Path, PureWindowsPath):
    """Path subclass for Windows systems.

    On a Windows system, instantiating a Path should return this object.
    """
    __slots__ = ()

    def owner(self):
        raise NotImplementedError("Path.owner() is unsupported on this system")

    def group(self):
        raise NotImplementedError("Path.group() is unsupported on this system")

    def is_mount(self):
        raise NotImplementedError("Path.is_mount() is unsupported on this system")
