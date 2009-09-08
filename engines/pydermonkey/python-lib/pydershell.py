import sys
import time
import threading
import traceback
import weakref
import types

import pydermonkey

class ContextWatchdogThread(threading.Thread):
    """
    Watches active JS contexts and triggers their operation callbacks
    at a regular interval.
    """

    # Default interval, in seconds, that the operation callbacks are
    # triggered at.
    DEFAULT_INTERVAL = 0.25

    def __init__(self, interval=DEFAULT_INTERVAL):
        threading.Thread.__init__(self)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._contexts = []
        self.interval = interval
        self.setDaemon(True)

    def add_context(self, cx):
        self._lock.acquire()
        try:
            self._contexts.append(weakref.ref(cx))
        finally:
            self._lock.release()

    def join(self):
        self._stop.set()
        threading.Thread.join(self)

    def run(self):
        while not self._stop.isSet():
            time.sleep(self.interval)
            new_list = []
            self._lock.acquire()
            try:
                for weakcx in self._contexts:
                    cx = weakcx()
                    if cx:
                        new_list.append(weakcx)
                        cx.trigger_operation_callback()
                self._contexts = new_list
            finally:
                self._lock.release()

# Create a global watchdog.
watchdog = ContextWatchdogThread()
watchdog.start()

class InternalError(BaseException):
    """
    Represents an error in a JS-wrapped Python function that wasn't
    expected to happen; because it's derived from BaseException, it
    unrolls the whole JS/Python stack so that the error can be
    reported to the outermost calling code.
    """

    def __init__(self):
        BaseException.__init__(self)
        self.exc_info = sys.exc_info()

class SafeJsObjectWrapper(object):
    """
    Securely wraps a JS object to behave like any normal Python object.
    """

    __slots__ = ['_jsobject', '_sandbox', '_this']

    def __init__(self, sandbox, jsobject, this):
        if not isinstance(jsobject, pydermonkey.Object):
            raise TypeError("Cannot wrap '%s' object" %
                            type(jsobject).__name__)
        object.__setattr__(self, '_sandbox', sandbox)
        object.__setattr__(self, '_jsobject', jsobject)
        object.__setattr__(self, '_this', this)

    @property
    def wrapped_jsobject(self):
        return self._jsobject

    def _wrap_to_python(self, jsvalue):
        return self._sandbox.wrap_jsobject(jsvalue, self._jsobject)

    def _wrap_to_js(self, value):
        return self._sandbox.wrap_pyobject(value)

    def __eq__(self, other):
        if isinstance(other, SafeJsObjectWrapper):
            return self._jsobject == other._jsobject
        else:
            return False

    def __str__(self):
        return self.toString()

    def __unicode__(self):
        return self.toString()

    def __setitem__(self, item, value):
        self.__setattr__(item, value)

    def __setattr__(self, name, value):
        cx = self._sandbox.cx
        jsobject = self._jsobject

        cx.define_property(jsobject, name,
                           self._wrap_to_js(value))

    def __getitem__(self, item):
        return self.__getattr__(item)

    def __getattr__(self, name):
        cx = self._sandbox.cx
        jsobject = self._jsobject

        return self._wrap_to_python(cx.get_property(jsobject, name))

    def __contains__(self, item):
        cx = self._sandbox.cx
        jsobject = self._jsobject

        return cx.has_property(jsobject, item)

    def __iter__(self):
        cx = self._sandbox.cx
        jsobject = self._jsobject

        properties = cx.enumerate(jsobject)
        for property in properties:
            yield property

class SafeJsFunctionWrapper(SafeJsObjectWrapper):
    """
    Securely wraps a JS function to behave like any normal Python object.
    """

    def __init__(self, sandbox, jsfunction, this):
        if not isinstance(jsfunction, pydermonkey.Function):
            raise TypeError("Cannot wrap '%s' object" %
                            type(jsobject).__name__)
        SafeJsObjectWrapper.__init__(self, sandbox, jsfunction, this)

    def __call__(self, *args):
        cx = self._sandbox.cx
        jsobject = self._jsobject
        this = self._this

        arglist = []
        for arg in args:
            arglist.append(self._wrap_to_js(arg))

        obj = cx.call_function(this, jsobject, tuple(arglist))
        return self._wrap_to_python(obj)

def format_stack(js_stack):
    """
    Returns a formatted Python-esque stack traceback of the given
    JS stack.
    """

    STACK_LINE  ="  File \"%(filename)s\", line %(lineno)d, in %(name)s"

    lines = []
    while js_stack:
        script = js_stack['script']
        function = js_stack['function']
        if script:
            frameinfo = dict(filename = script.filename,
                             lineno = js_stack['lineno'],
                             name = '<module>')
        elif function and not function.is_python:
            frameinfo = dict(filename = function.filename,
                             lineno = js_stack['lineno'],
                             name = function.name)
        else:
            frameinfo = None
        if frameinfo:
            lines.insert(0, STACK_LINE % frameinfo)
            try:
                filelines = open(frameinfo['filename']).readlines()
                line = filelines[frameinfo['lineno'] - 1].strip()
                lines.insert(1, "    %s" % line)
            except Exception:
                pass
        js_stack = js_stack['caller']
    lines.insert(0, "Traceback (most recent call last):")
    return '\n'.join(lines)

def jsexposed(name=None, on=None):
    """
    Decorator used to expose the decorated function or method to
    untrusted JS.

    'name' is an optional alternative name for the function.

    'on' is an optional SafeJsObjectWrapper that the function can be
    automatically attached as a property to.
    """

    if callable(name):
        func = name
        func.__jsexposed__ = True
        return func

    def make_exposed(func):
        if name:
            func.__name__ = name
        func.__jsexposed__ = True
        if on:
            on[func.__name__] = func
        return func
    return make_exposed

class JsExposedObject(object):
    """
    Trivial base/mixin class for any Python classes that choose to
    expose themselves to JS code.
    """

    pass

class JsSandbox(object):
    """
    A JS runtime and associated functionality capable of securely
    loading and executing scripts.
    """

    def __init__(self, watchdog=watchdog):
        rt = pydermonkey.Runtime()
        cx = rt.new_context()
        root = cx.new_object()
        cx.init_standard_classes(root)

        cx.set_operation_callback(self._opcb)
        cx.set_throw_hook(self._throwhook)
        watchdog.add_context(cx)

        self.rt = rt
        self.cx = cx
        self.curr_exc = None
        self.py_stack = None
        self.js_stack = None
        self.__py_to_js = {}
        self.__type_protos = {}
        self.root = self.wrap_jsobject(root, root)

    def finish(self):
        """
        Cleans up all resources used by the sandbox, breaking any reference
        cycles created due to issue #2 in pydermonkey:

        http://code.google.com/p/pydermonkey/issues/detail?id=2
        """

        for jsobj in self.__py_to_js.values():
            self.cx.clear_object_private(jsobj)
        del self.__py_to_js
        del self.__type_protos
        del self.curr_exc
        del self.py_stack
        del self.js_stack
        del self.cx
        del self.rt

    def _opcb(self, cx):
        # Don't do anything; if a keyboard interrupt was triggered,
        # it'll get raised here automatically.
        pass

    def _throwhook(self, cx):
        curr_exc = cx.get_pending_exception()
        if self.curr_exc != curr_exc:
            self.curr_exc = curr_exc
            self.py_stack = traceback.extract_stack()
            self.js_stack = cx.get_stack()

    def __wrap_pycallable(self, func, pyproto=None):
        if func in self.__py_to_js:
            return self.__py_to_js[func]

        if hasattr(func, '__name__'):
            name = func.__name__
        else:
            name = ""

        if pyproto:
            def wrapper(func_cx, this, args):
                try:
                    arglist = []
                    for arg in args:
                        arglist.append(self.wrap_jsobject(arg))
                    instance = func_cx.get_object_private(this)
                    if instance is None or not isinstance(instance, pyproto):
                        raise pydermonkey.error("Method type mismatch")

                    # TODO: Fill in extra required params with
                    # pymonkey.undefined?  or automatically throw an
                    # exception to calling js code?
                    return self.wrap_pyobject(func(instance, *arglist))
                except pydermonkey.error:
                    raise
                except Exception:
                    raise InternalError()
        else:
            def wrapper(func_cx, this, args):
                try:
                    arglist = []
                    for arg in args:
                        arglist.append(self.wrap_jsobject(arg))

                    # TODO: Fill in extra required params with
                    # pymonkey.undefined?  or automatically throw an
                    # exception to calling js code?
                    return self.wrap_pyobject(func(*arglist))
                except pydermonkey.error:
                    raise
                except Exception:
                    raise InternalError()
        wrapper.wrapped_pyobject = func
        wrapper.__name__ = name

        jsfunc = self.cx.new_function(wrapper, name)
        self.__py_to_js[func] = jsfunc

        return jsfunc

    def __wrap_pyinstance(self, value):
        pyproto = type(value)
        if pyproto not in self.__type_protos:
            jsproto = self.cx.new_object()
            if hasattr(pyproto, '__jsprops__'):
                define_getter = self.cx.get_property(jsproto,
                                                     '__defineGetter__')
                define_setter = self.cx.get_property(jsproto,
                                                     '__defineSetter__')
                for name in pyproto.__jsprops__:
                    prop = getattr(pyproto, name)
                    if not type(prop) == property:
                        raise TypeError("Expected attribute '%s' to "
                                        "be a property" % name)
                    getter = None
                    setter = None
                    if prop.fget:
                        getter = self.__wrap_pycallable(prop.fget,
                                                        pyproto)
                    if prop.fset:
                        setter = self.__wrap_pycallable(prop.fset,
                                                        pyproto)
                    if getter:
                        self.cx.call_function(jsproto,
                                              define_getter,
                                              (name, getter))
                    if setter:
                        self.cx.call_function(jsproto,
                                              define_setter,
                                              (name, setter,))
            for name in dir(pyproto):
                attr = getattr(pyproto, name)
                if (isinstance(attr, types.UnboundMethodType) and
                    hasattr(attr, '__jsexposed__') and
                    attr.__jsexposed__):
                    jsmethod = self.__wrap_pycallable(attr, pyproto)
                    self.cx.define_property(jsproto, name, jsmethod)
            self.__type_protos[pyproto] = jsproto
        return self.cx.new_object(value, self.__type_protos[pyproto])

    def wrap_pyobject(self, value):
        """
        Wraps the given Python object for export to untrusted JS.

        If the Python object isn't of a type that can be exposed to JS,
        a TypeError is raised.
        """

        if (isinstance(value, (int, basestring, float, bool)) or
            value is pydermonkey.undefined or
            value is None):
            return value
        if isinstance(value, SafeJsObjectWrapper):
            # It's already wrapped, just unwrap it.
            return value.wrapped_jsobject
        elif callable(value):
            if not (hasattr(value, '__jsexposed__') and
                    value.__jsexposed__):
                raise ValueError("Callable isn't configured for exposure "
                                 "to untrusted JS code")
            return self.__wrap_pycallable(value)
        elif isinstance(value, JsExposedObject):
            return self.__wrap_pyinstance(value)
        else:
            raise TypeError("Can't expose objects of type '%s' to JS." %
                            type(value).__name__)

    def wrap_jsobject(self, jsvalue, this=None):
        """
        Wraps the given pydermonkey.Object for import to trusted
        Python code. If the type is just a primitive, it's simply
        returned, since no wrapping is needed.
        """

        if this is None:
            this = self.root.wrapped_jsobject
        if isinstance(jsvalue, pydermonkey.Function):
            if jsvalue.is_python:
                # It's a Python function, just unwrap it.
                return self.cx.get_object_private(jsvalue).wrapped_pyobject
            return SafeJsFunctionWrapper(self, jsvalue, this)
        elif isinstance(jsvalue, pydermonkey.Object):
            # It's a wrapped Python object instance, just unwrap it.
            instance = self.cx.get_object_private(jsvalue)
            if instance:
                if not isinstance(instance, JsExposedObject):
                    raise AssertionError("Object private is not of type "
                                         "JsExposedObject")
                return instance
            else:
                return SafeJsObjectWrapper(self, jsvalue, this)
        else:
            # It's a primitive value.
            return jsvalue

    def new_array(self, *contents):
        array = self.wrap_jsobject(self.cx.new_array_object())
        for item in contents:
            array.push(item)
        return array

    def new_object(self, **contents):
        obj = self.wrap_jsobject(self.cx.new_object())
        for name in contents:
            obj[name] = contents[name]
        return obj

    def evaluate(self, code, filename='<string>', lineno=1):
        retval = self.cx.evaluate_script(self.root.wrapped_jsobject,
                                         code, filename, lineno)
        return self.wrap_jsobject(retval)

    def run_script(self, filename, callback=None):
        """
        Runs the given JS script, returning 0 on success, -1 on failure.
        """

        retval = -1
        contents = open(filename).read()
        cx = self.cx
        try:
            result = cx.evaluate_script(self.root.wrapped_jsobject,
                                        contents, filename, 1)
            if callback:
                callback(self.wrap_jsobject(result))
            retval = 0
        except pydermonkey.error, e:
            print format_stack(self.js_stack)
            print e.args[1]
        except InternalError, e:
            print "An internal error occurred."
            traceback.print_tb(e.exc_info[2])
            print e.exc_info[1]
        return retval
