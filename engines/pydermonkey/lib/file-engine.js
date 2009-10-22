
var exports = require('./file');

exports.SEPARATOR = '/';

exports.cwd = function () {
  return pyder.cwd();
};

exports.list = function (path) {
  return pyder.listDirectory(path);
};

exports.canonical = function (path) {
  return pyder.canonical(path);
};

exports.exists = function (path) {
  return pyder.exists(path);
};

// TODO necessary for lazy module reloading in sandboxes
exports.mtime = function (path) {
  return pyder.stat(path).mtime;
};

exports.size = function (path) {
  return pyder.stat(path).size;
};

exports.stat = function (path) {
  return pyder.stat(path);
};

exports.isDirectory = function (path) {
  return pyder.isDirectory(path);
};

exports.isFile = function (path) {
  return pyder.isFile(path);
};

exports.isLink = function (path) {
    throw Error("isLink not yet implemented.");
};

exports.isReadable = function (path) {
    throw Error("isReadable not yet implemented.");
};

exports.isWritable = function (path) {
    throw Error("isWritable not yet implemented.");
};

exports.rename = function (source, target) {
    throw Error("rename not yet implemented.");
};

exports.move = function (source, target) {
    throw Error("move not yet implemented.");
};

exports.remove = function (path) {
    throw Error("remove not yet implemented.");
};

exports.mkdir = function (path) {
    throw Error("mkdir not yet implemented.");
};

exports.rmdir = function(path) {
    throw Error("rmdir not yet implemented.");
};

exports.touch = function (path, mtime) {
    throw Error("touch not yet implemented.");
};

// FIXME temporary hack
var readfile = system.fs.read; // from bootstrap system object

exports.FileIO = function (path, mode, permissions) {
    mode = exports.mode(mode);
    var read = mode.read,
        write = mode.write,
        append = mode.append,
        update = mode.update;

    if (update) {
        throw new Error("Updating IO not yet implemented.");
    } else if (write || append) {
        throw new Error("Writing IO not yet implemented.");
    } else if (read) {
        // FIXME temporary hack
        return {
            'read': function () {
                return readfile(path);
            },
            'close': function () {
            }
        };
    } else {
        throw new Error("Files must be opened either for read, write, or update mode.");
    }
};

