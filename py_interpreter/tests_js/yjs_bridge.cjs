// Interoperability fixture: the exact browser bundle, not a second JS implementation.
const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const runtime = {TextEncoder, TextDecoder, crypto: require('node:crypto').webcrypto,
    setTimeout, clearTimeout, setInterval, clearInterval, console, Uint8Array, ArrayBuffer, Map, Set};
vm.createContext(runtime);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/py_interpreter/vendor/yjs.js'), 'utf8'), runtime);
const Y = runtime.CourseCodeY, input = JSON.parse(fs.readFileSync(0, 'utf8')), doc = new Y.Doc();
Y.applyUpdate(doc, Uint8Array.from(Buffer.from(input.state, 'base64')));
const before = Y.encodeStateVector(doc);
if (input.insert) doc.getText('code').insert(0, input.insert);
process.stdout.write(JSON.stringify({code: doc.getText('code').toString(),
    update: Buffer.from(Y.encodeStateAsUpdate(doc, before)).toString('base64')}));
doc.destroy();
