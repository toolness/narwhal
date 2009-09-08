import os
import sys
import traceback

import pydermonkey
from pydershell import JsSandbox, JsExposedObject, jsexposed

class NarwhalRunner(object):
    def __init__(self, argv, home_dir, engine_home_dir):
        self.argv = argv
        self.home_dir = home_dir
        self.engine_home_dir = engine_home_dir
        self.sandbox = JsSandbox()
        self.sandbox.root['global'] = pydermonkey.undefined

    def run(self):
        filename = os.path.join(self.home_dir, 'narwhal.js')
        return self.sandbox.run_script(filename,
                                       self.__call_narwhal)

    def _real_path(self, path):
        path = self.home_dir + path
        path = os.path.normpath(path)
        path = os.path.realpath(path)
        if not path.startswith(self.home_dir):
            return None
        return path

    def __make_system_object(self):
        fs = self.sandbox.new_object()

        @jsexposed(on=fs)
        def read(filename, args=None):
            path = self._real_path(filename)
            if not path:
                raise pydermonkey.error("invalid filename: %s" % filename)
            contents = open(path).read()
            if args and args.charset:
                contents = contents.decode(args.charset)
            return contents

        @jsexposed(on=fs)
        def isFile(filename):
            path = self._real_path(filename)
            if not path:
                return False
            return os.path.isfile(path)

        system = self.sandbox.new_object(
            engine = 'pydermonkey',
            engines = self.sandbox.new_array('pydermonkey', 'default'),
            os = sys.platform,
            prefix = '',
            prefixes = self.sandbox.new_array(''),
            debug = False,
            verbose = False,
            fs = fs
            )
        system['global'] = self.sandbox.root

        @jsexposed(on=system, name='print')
        def jsprint(*args):
            print args

        @jsexposed(on=system)
        def evalGlobal(*args):
            raise NotImplementedError("evalGlobal not implemented")

        @jsexposed(on=system)
        def evaluate(code, filename='<string>', lineno=1):
            filename = self.home_dir + filename
            code = ("function(require,exports,module,system,print){"
                    "%s\n// */\n}" % code)
            return self.sandbox.evaluate(code, filename, lineno)

        return system

    def __call_narwhal(self, narwhal):
        narwhal(self.__make_system_object())

def run(*args, **kwargs):
    runner = NarwhalRunner(*args, **kwargs)
    return runner.run()
