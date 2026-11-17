/*!
 * PelaReeflet PoW worker v1.0
 * © 2026 PelagicBeacon（PELAGIC BEACON）· MIT 协议，见 LICENSE
 *
 * 与主线程约定：
 *   收 {challenge, prefix, start, step}
 *   发 {type:'found', nonce} / {type:'progress', tried}
 */
'use strict';

var K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
]);
var W = new Uint32Array(64);
var OB = new Uint8Array(32);

function sha256Hex(bytes, len) {
  var H0 = 0x6a09e667, H1 = 0xbb67ae85, H2 = 0x3c6ef372, H3 = 0xa54ff53a,
      H4 = 0x510e527f, H5 = 0x9b05688c, H6 = 0x1f83d9ab, H7 = 0x5be0cd19;

  var bitLen = len * 8;
  bytes[len] = 0x80;
  var total = len + 1;
  while (total % 64 !== 56) { bytes[total++] = 0; }

  bytes[total++] = 0; bytes[total++] = 0; bytes[total++] = 0; bytes[total++] = 0;
  bytes[total++] = (bitLen >>> 24) & 0xff;
  bytes[total++] = (bitLen >>> 16) & 0xff;
  bytes[total++] = (bitLen >>> 8) & 0xff;
  bytes[total++] = bitLen & 0xff;

  for (var off = 0; off < total; off += 64) {
    for (var i = 0; i < 16; i++) {
      var j = off + i * 4;
      W[i] = (bytes[j] << 24) | (bytes[j + 1] << 16) | (bytes[j + 2] << 8) | bytes[j + 3];
    }
    for (i = 16; i < 64; i++) {
      var w15 = W[i - 15], w2 = W[i - 2];
      var s0 = ((w15 >>> 7) | (w15 << 25)) ^ ((w15 >>> 18) | (w15 << 14)) ^ (w15 >>> 3);
      var s1 = ((w2 >>> 17) | (w2 << 15)) ^ ((w2 >>> 19) | (w2 << 13)) ^ (w2 >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) | 0;
    }

    var a = H0, b = H1, c = H2, d = H3, e = H4, f = H5, g = H6, h = H7;
    for (i = 0; i < 64; i++) {
      var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      var ch = (e & f) ^ (~e & g);
      var t1 = (h + S1 + ch + K[i] + W[i]) | 0;
      var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      var maj = (a & b) ^ (a & c) ^ (b & c);
      var t2 = (S0 + maj) | 0;
      h = g; g = f; f = e; e = (d + t1) | 0;
      d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    H0 = (H0 + a) | 0; H1 = (H1 + b) | 0; H2 = (H2 + c) | 0; H3 = (H3 + d) | 0;
    H4 = (H4 + e) | 0; H5 = (H5 + f) | 0; H6 = (H6 + g) | 0; H7 = (H7 + h) | 0;
  }

  var hs = [H0, H1, H2, H3, H4, H5, H6, H7];
  for (var k = 0; k < 8; k++) {
    var v = hs[k];
    OB[k * 4] = (v >>> 24) & 0xff;
    OB[k * 4 + 1] = (v >>> 16) & 0xff;
    OB[k * 4 + 2] = (v >>> 8) & 0xff;
    OB[k * 4 + 3] = v & 0xff;
  }
  return OB;
}

var enc = new TextEncoder();
var msgBuf = new Uint8Array(256);
var stopped = false;

self.onmessage = function (e) {
  var job = e.data || {};
  if (job.type === 'stop') { stopped = true; return; }

  var base = job.challenge + ':';
  var prefix = job.prefix | 0;
  var step = Math.max(1, job.step | 0);
  var nonce = job.start | 0;
  var fullBytes = prefix >> 1;
  var odd = prefix & 1;
  var batch = 0;

  while (!stopped) {
    var b = enc.encode(base + nonce);
    msgBuf.set(b);
    var out = sha256Hex(msgBuf, b.length);

    var ok = true;
    for (var i = 0; i < fullBytes; i++) {
      if (out[i] !== 0) { ok = false; break; }
    }
    if (ok && odd && (out[fullBytes] >> 4) !== 0) ok = false;

    if (ok) { self.postMessage({ type: 'found', nonce: nonce }); return; }

    nonce += step;
    batch++;
    if (batch >= 2000) { batch = 0; self.postMessage({ type: 'progress', tried: 2000 }); }
  }
};
