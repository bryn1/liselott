/* T5.3 — client-side downscale BEFORE an upload (OQ-2 ruling b, P1-1).
 *
 * Why this exists: the vm106 lane refuses request bodies over ≈1 MiB at the
 * nginx edge (measured: 1,000,000 B passes, 1,200,000 B → 413 before any app),
 * and the APP holds its own line lower — tillagg.MAX_UPLOAD, 900000 bytes — so a
 * phone-camera PNG must never reach either wall. The browser downscales on a
 * canvas to ≤680×1020 (the normalized cover is ≤340×510; this leaves 2× for
 * crisp hidpi and nothing more) and re-encodes as JPEG walking the quality
 * ladder 0.85 → 0.75 → 0.6 while the blob is still over 900000 bytes. If the
 * ladder is exhausted and the blob is STILL over, it refuses to POST and says
 * so in Swedish, inline — the server repeats the same cap regardless, because
 * the browser is courtesy, not security. */
(function () {
  "use strict";

  var OMSLAG_MAX_W = 680;
  var OMSLAG_MAX_H = 1020;
  var OMSLAG_MAX_BYTES = 900000;            // tillagg.MAX_UPLOAD — the ONE budget
  var OMSLAG_QUALITY_LADDER = [0.85, 0.75, 0.6];

  function show(node, msg) {
    if (!node) return;
    node.textContent = msg;
    node.hidden = false;
  }

  function encode(canvas, ladder, maxBytes, done) {
    if (!ladder.length) { done(null); return; }
    var q = ladder.shift();
    canvas.toBlob(function (blob) {
      if (!blob) { done(null); return; }
      if (blob.size <= maxBytes) { done(blob); return; }
      encode(canvas, ladder, maxBytes, done);   // walk the ladder while over
    }, "image/jpeg", q);
  }

  function downscale(file, done) {
    var url = URL.createObjectURL(file);
    var img = new Image();
    img.onerror = function () { URL.revokeObjectURL(url); done(null); };
    img.onload = function () {
      var scale = Math.min(1, OMSLAG_MAX_W / img.width, OMSLAG_MAX_H / img.height);
      var canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(img.width * scale));
      canvas.height = Math.max(1, Math.round(img.height * scale));
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      encode(canvas, OMSLAG_QUALITY_LADDER.slice(), OMSLAG_MAX_BYTES, done);
    };
    img.src = url;
  }

  document.querySelectorAll("form.uppladdning").forEach(function (form) {
    form.addEventListener("submit", function (ev) {
      var input = form.querySelector("input[type=file]");
      var err = document.getElementById("uppladdningsfel");
      var file = input && input.files && input.files[0];
      if (!file) return;                      // the server answers 400 honestly
      ev.preventDefault();                    // async guard before the real POST
      if (err) err.hidden = true;
      downscale(file, function (blob) {
        if (blob === null) {                  // unreadable/undecodable here —
          show(err, "Bilden kunde inte läsas här — skickas som den är, " +
                    "servern kontrollerar den.");   // the server still holds the line
          form.submit();
          return;
        }
        if (blob.size > OMSLAG_MAX_BYTES) {   // ladder exhausted: DO NOT POST
          show(err, "Bilden är för stor — ladda upp en mindre fil");
          return;
        }
        var dt = new DataTransfer();
        dt.items.add(new File([blob], "omslag.jpg", { type: "image/jpeg" }));
        input.files = dt.files;
        form.submit();
      });
    });
  });
}());
