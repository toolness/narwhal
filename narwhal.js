(function (system) {

// logger shim
var shim = function () {
    if (system.debug && system.print) {
        system.print(Array.prototype.join.apply(arguments, [" "]));
    }
};
var log = {fatal:shim, error:shim, warn:shim, info:shim, debug:shim};
system.log = log;

// global reference
global = system.global;
global.system = system;
global.print = system.print;

// equivalent to "var sandbox = require('sandbox');"
var sandboxFactory = system.evaluate(
    system.fs.read(system.prefix + "/lib/sandbox.js"),
    "sandbox.js",
    1
);
var sandbox = {};
sandboxFactory(null, sandbox, system, system.print);

// construct the initial paths
var paths = [
    system.prefix + '/stdlib',
    system.prefix + '/lib'
];
for (var i = 0; i < system.platforms.length; i++) {
    var platform = system.platforms[i];
    paths.push(system.prefix + '/platforms/' + platform + '/stdlib');
    paths.push(system.prefix + '/platforms/' + platform + '/lib');
}

// create the primary Loader and Sandbox:
var loader = sandbox.Loader({paths: paths});
var modules = {system: system, sandbox: sandbox};
global.require = sandbox.Sandbox({loader: loader, modules: modules});

// patch the primordials (or: save the whales)
// to bring them up to at least the neighborhood of ES5 compliance.
try {
    require("global");
} catch (e) {
    system.log.error("Couldn't load global/primordial patches ("+e+")");
}

// load the complete system module
global.require.force("system");

// parse command line options
var parser = require("narwhal").parser;
var options = parser.parse(system.args);
system.packagePrefixes = [system.prefix];
system.packagePrefixes.unshift.apply(system.packagePrefixes, options.packagePrefies);
system.debug = options.debug;

// enable loader tracing
global.require.debug = options.verbose;
// in verbose mode, list all the modules that are 
// already loaded
if (options.verbose) {
    Object.keys(modules).forEach(function (name) {
        print('@ ' + name);
    });
}

// find the program module and its prefix
var program;
if (system.args.length && !options.interactive && !options.main) {
    if (!program)
        program = system.fs.path(system.args[0]).canonical();

    // add package prefixes for all of the packages
    // containing the program, from specific to general
    var parts = system.fs.split(program);
    for (var i = 0; i < parts.length; i++) {
        var path = system.fs.join.apply(null, parts.slice(0, i));
        var packageJson = system.fs.join(path, 'package.json');
        if (system.fs.isFile(packageJson))
            system.packagePrefixes.unshift(path);
    }

    if (program.isDirectory()) {
        if (!program.join('package.json').isFile())
            throw new Error("Program directory does not contain a package.json");
        system.packagePrefixes.unshift(program);
    }
}

// load packages
var packages;
if (!options.noPackages) {
    try {
        packages = require("packages");
        packages.main();
    } catch (e) {
        system.log.error("Warning: Couldn't load packages. Packages won't be available. ("+e+")");
    }
} else {
    packages = {
        catalog: {},
        packageOrder: []
    }
}

// run command options
//  -I, --include lib
//  -r, --require module
//  -e, -c , --command command
//  -:, --path delimiter
options.todo.forEach(function (item) {
    var action = item[0];
    var value = item[1];
    if (action == "include") {
        require.paths.unshift(value);
    } else if (action == "require") {
        require(value);
    } else if (action == "eval") {
        system.evalGlobal(value);
    } else if (action == "path") {
        var paths = packages.packageOrder.map(function (pkg) {
            return pkg.directory.join('bin');
        }).filter(function (path) {
            return path.isDirectory();
        });
        var oldPaths = system.env.PATH.split(value);
        while (oldPaths.length) {
            var path = oldPaths.shift();
            if (paths.indexOf(path) < 0)
                paths.push(path);
        }
        print(paths.join(value));
    }
});

// load the program module
if (options.main) {
    require(options.main);
} else if (program) {
    if (program.isDirectory()) {
        require(packages.root.directory.resolve(packages.root.main || 'main').toString());
    } else {
        require(program.toString());
    }
}

// send an unload event if that module has been required
if (require.loader.isLoaded('unload')) {
    require('unload').send();
}

})
