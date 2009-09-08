exports.args = pyder.info.argv;
exports.env = {};

exports.stdout = {
  write: function() {
    pyder.printString.apply(pyder, arguments);
  },
  flush: function() {}
};

exports.stderr = exports.stdout;

//var IO = require("./io").IO;

//exports.stdin  = /*TODO*/
//exports.stdout = /*TODO*/
//exports.stderr = /*TODO*/

//exports.args = [/*TODO*/];

//exports.env = {}; /*TODO*/

//exports.fs = require('./file');

// default logger
//var Logger = require("./logger").Logger;
//exports.log = new Logger(exports.stdout);

