(function(global, evalGlobal) {
   var filename = '/narwhal.js';
   var code = pyder.read(filename);
   var narwhal = pyder.evaluate(code, filename, 1);
   var system = {
     global: global,
     evalGlobal: evalGlobal,
     engine: 'pydermonkey',
     engines: ['pydermonkey', 'default'],
     os: pyder.info.os,
     print: function print() {
       pyder.printString.apply(pyder, arguments);
     },
     fs: {
       read: function read() {
         return pyder.read.apply(pyder, arguments);
       },
       isFile: function isFile() {
         return pyder.isFile.apply(pyder, arguments);
       }
     },
     prefix: "",
     prefixes: [""],
     evaluate: function evaluate(code, filename, lineno) {
       code = ("function(require,exports,module,system,print){" +
               code +
               "\n// */\n}");
       return pyder.evaluate(code, filename, lineno);
     },
     debug: false,
     verbose: false
   };
   narwhal(system);
})(this, function () {
    return eval(arguments[0]);
});
