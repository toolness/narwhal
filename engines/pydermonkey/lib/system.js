exports.args = pyder.info.argv;
exports.env = {};

exports.stdout = (function() {
    var buffer = [];
    return {
        write: function(text) {
            buffer.push(text.toString());
            return this;
        },
        flush: function() {
            pyder.printString(buffer.join(""));
            buffer = [];
        }
    };
})();

exports.stderr = exports.stdout;

var Logger = require("./logger").Logger;
exports.log = new Logger(
  {write: function(message) {
     pyder.printString(message + '\n');
   }
  });

//var IO = require("./io").IO;

//exports.stdin  = /*TODO*/
//exports.stdout = /*TODO*/
//exports.stderr = /*TODO*/

//exports.args = [/*TODO*/];

//exports.env = {}; /*TODO*/

exports.fs = require('./file');

exports.env = {
  get PWD() {
    return pyder.cwd();
  }
};

// default logger
//var Logger = require("./logger").Logger;
//exports.log = new Logger(exports.stdout);

