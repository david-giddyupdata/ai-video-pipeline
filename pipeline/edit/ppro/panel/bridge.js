// The pipeline's line into Premiere: a localhost HTTP server that runs the ExtendScript it is sent (aidvRun in
// jsx/aidv.jsx) and answers with its JSON result. Bound to 127.0.0.1 and guarded by a token that only this user's
// profile can read (~/.giddyup/ppro_bridge.json, rewritten at every start). Loaded by bridge.html (hidden, starts
// with Premiere) and by the AIDV panel. The panel serves only when the hidden bridge doesn't answer: two servers
// writing one info file stranded the hidden one once the panel closed (Fable's review, 2026-10-13).
(function () {
  var http = require("http"), fs = require("fs"), path = require("path"), os = require("os"), crypto = require("crypto");
  var info = path.join(os.homedir(), ".giddyup", "ppro_bridge.json");
  var token = crypto.randomBytes(16).toString("hex");
  var ext = decodeURIComponent(window.__adobe_cep__.getSystemPath("extension")).replace(/^file:\/*/, "");
  var jsx = JSON.stringify(path.join(ext, "jsx", "aidv.jsx").split(path.sep).join("/"));

  function lit(s) {
    return JSON.stringify(s).split(String.fromCharCode(0x2028)).join("\\u2028")
                            .split(String.fromCharCode(0x2029)).join("\\u2029");     // ES3 line breaks
  }
  // aidv.jsx is (re)loaded when missing, when its content changed since this bridge last loaded it, or when a call
  // asks, so an edit to it needs no restart and no flag (an idea from the premiere-pro-mcp project, 2026-10-13).
  var loaded = null;
  function evalScript(code, done, reload) {
    var hash = crypto.createHash("sha1").update(fs.readFileSync(JSON.parse(jsx))).digest("hex");
    var fresh = reload || hash !== loaded;
    loaded = hash;
    window.__adobe_cep__.evalScript((fresh ? "" : "if (typeof aidvRun !== 'function') ") + "$.evalFile(" + jsx +
                                    "); aidvRun(" + lit(code) + ")", done);
  }
  window.aidvEval = evalScript;

  var server = http.createServer(function (req, res) {
    if (req.method !== "POST" || req.headers["x-aidv-token"] !== token) {
      res.writeHead(403);
      return res.end();
    }
    var body = "";
    req.setEncoding("utf8");
    req.on("data", function (c) { body += c; });
    req.on("end", function () {
      var msg;
      try { msg = JSON.parse(body); } catch (e) { res.writeHead(400); return res.end(); }
      evalScript(msg.code, function (out) {
        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(out);
      }, msg.reload);
    });
  });
  function serve() {
    server.listen(0, "127.0.0.1", function () {
      fs.mkdirSync(path.dirname(info), { recursive: true });
      fs.writeFileSync(info, JSON.stringify({ port: server.address().port, token: token, pid: process.pid,
                                              started: new Date().toISOString() }));
    });
  }
  if (window.__adobe_cep__.getExtensionId() === "com.giddyup.aidv.bridge") {
    return serve();
  }
  var live;                                         // the panel: is the hidden bridge answering?
  try { live = JSON.parse(fs.readFileSync(info, "utf8")); } catch (e) { live = null; }
  if (!live) { return serve(); }
  var probe = http.request({ host: "127.0.0.1", port: live.port, method: "POST", path: "/", timeout: 2000,
                             headers: { "x-aidv-token": live.token, "Content-Type": "application/json" } },
                           function (res) { if (res.statusCode !== 200) { serve(); } res.resume(); });
  probe.on("error", serve);
  probe.on("timeout", function () { probe.destroy(); });
  probe.end(JSON.stringify({ code: "true" }));
})();
