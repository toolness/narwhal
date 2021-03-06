import os
import sys
import traceback

import pydermonkey
from pydershell import JsSandbox, JsExposedObject, jsexposed

class PyderApi(JsExposedObject):
    __jsprops__ = ['info']

    def __init__(self, runner):
        self._runner = runner
        self._sandbox = runner.sandbox
        self._root_dir = runner.home_dir
        self._cwd = '/'

    def _sandboxed_path(self, path):
        if not path.startswith(self._root_dir):
            raise AssertionError("path can't be sandboxed")
        if path == self._root_dir:
            return '/'
        else:
            # TODO: If on Windows, this needs to be converted
            # to a unix-style path, since the sandbox uses
            # unix-style paths.
            return path[len(self._root_dir):]

    def _real_path(self, path):
        if not path.startswith('/'):
            if self._cwd == '/':
                path = '/' + path
            else:
                path = '/'.join([self._cwd, path])

        # TODO: May need to change this for Windows.
        path = self._root_dir + path

        path = os.path.normpath(path)
        path = os.path.realpath(path)
        if not path.startswith(self._root_dir):
            return None
        return path

    @property
    def info(self):
        argv = ['/bin/narwhal'] + sys.argv[1:]
        return self._sandbox.new_object(
            os = sys.platform,
            argv = self._sandbox.new_array(*argv)
            );

    @jsexposed
    def cwd(self):
        return self._cwd

    @jsexposed
    def exit(self, code):
        if not code:
            code = 0
        elif type(code) != int:
            code = -1
        sys.exit(code)

    @jsexposed
    def read(self, filename, args=None):
        path = self._real_path(filename)
        if not path:
            raise pydermonkey.error("invalid filename: %s" % filename)
        try:
            contents = open(path).read()
        except IOError, e:
            raise pydermonkey.error(str(e))
        # TODO: Should we really be ignoring errors here?
        if args and args.charset:
            contents = contents.decode(args.charset, 'ignore')
        else:
            # TODO: Inflate the string instead?
            contents = contents.decode('utf-8', 'ignore')
        return contents

    @jsexposed
    def stat(self, filename):
        path = self._real_path(filename)
        if not path or not os.path.exists(path):
            return None
        info = os.stat(path)
        return self._sandbox.new_object(
            mtime = info.st_mtime,
            size = int(info.st_size)
            )

    @jsexposed
    def canonical(self, path):
        path = self._real_path(path)
        if not path:
            # TODO: Throw an exception instead?
            return None
        return self._sandboxed_path(path)

    @jsexposed
    def exists(self, path):
        path = self._real_path(path)
        if not path:
            return False
        return os.path.exists(path)

    @jsexposed
    def isFile(self, filename):
        path = self._real_path(filename)
        if not path:
            return False
        return os.path.isfile(path)

    @jsexposed
    def isDirectory(self, filename):
        path = self._real_path(filename)
        if not path:
            return False
        return os.path.isdir(path)

    @jsexposed
    def listDirectory(self, filename):
        path = self._real_path(str(filename))
        dirs = []
        if path and os.path.isdir(path):
            dirs.extend(os.listdir(path))
        return self._sandbox.new_array(*dirs)

    @jsexposed
    def printString(self, *args):
        sys.stdout.write(" ".join(args))

    @jsexposed
    def evaluate(self, code, filename='<string>', lineno=1):
        if filename != '<string>':
            filename = self._root_dir + filename
        return self._sandbox.evaluate(code, filename, lineno)

class NarwhalRunner(object):
    def __init__(self, argv, home_dir, engine_home_dir):
        self.argv = argv
        self.home_dir = home_dir
        self.engine_home_dir = engine_home_dir
        self.sandbox = JsSandbox()
        self.sandbox.root.pyder = PyderApi(self)

    def run(self):
        filename = os.path.join(self.engine_home_dir, 'bootstrap.js')
        return self.sandbox.run_script(filename)

def run(*args, **kwargs):
    runner = NarwhalRunner(*args, **kwargs)
    return runner.run()
