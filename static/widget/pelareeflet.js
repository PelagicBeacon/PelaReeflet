/*!
 * PelaReeflet 人机验证组件 v1.0
 * © 2026 PelagicBeacon（PELAGIC BEACON）· MIT 协议，见 LICENSE
 *
 * 嵌入方式：
 *   <script src="https://reeflet.example.com/embed/pelareeflet.js" async defer></script>
 *   <div class="pelareeflet" data-callback="onReefletToken"></div>
 *
 * 回调拿到的是 ticket，交给自己的后端调用 /api/v1/siteverify 换结论。
 */
(function (global) {
  'use strict';

  if (global.PelaReeflet) return;

  var SCRIPT = document.currentScript || (function () {
    var all = document.getElementsByTagName('script');
    for (var i = all.length - 1; i >= 0; i--) {
      if (all[i].src && all[i].src.indexOf('pelareeflet.js') !== -1) return all[i];
    }
    return null;
  })();

  var ORIGIN = (function () {
    try { return new URL(SCRIPT.src).origin; } catch (e) { return ''; }
  })();

  function api(path) { return ORIGIN + path; }

  var STYLE_ID = 'pelareeflet-style';

  // 统一日志前缀，方便在 DevTools 里 grep 出卡在哪一步
  function log() {
    try {
      var args = ['[PelaReeflet]'].concat([].slice.call(arguments));
      console.log.apply(console, args);
    } catch (e) {}
  }

  var CSS = ''
    + '.prf-gate{--prf-bg:#000;--prf-bd:#3c3c3c;--prf-in:#5e5e5e;--prf-fg:#f0f0f0;'
    + '--prf-sub:#8a8a8a;--prf-dim:#969696;--prf-accent:#4e8ee0;--prf-ok:#2ea868;--prf-err:#d4544c;'
    + 'display:block;box-sizing:border-box;width:100%;max-width:344px;'
    + 'background:var(--prf-bg);border:1px solid var(--prf-bd);border-radius:2px;'
    + 'color:var(--prf-fg);padding:6px;outline:none;user-select:none;'
    + 'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,'
    + '"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;'
    + 'font-size:13px;line-height:1.4;-webkit-font-smoothing:antialiased}'
    + '.prf-gate--light{--prf-bg:#fff;--prf-bd:#d6d6d6;--prf-in:#c9c9c9;--prf-fg:#161616;'
    + '--prf-sub:#8a8a8a;--prf-dim:#8a8a8a}'
    + '.prf-gate:focus-visible{outline:2px solid var(--prf-accent);outline-offset:2px}'

    + '.prf-gate__slot{box-sizing:border-box;border:1px solid var(--prf-in);'
    + 'border-radius:2px;padding:8px 10px;background:var(--prf-bg)}'
    + '.prf-gate__row{display:flex;align-items:center;gap:10px;min-height:30px}'
    + '.prf-gate__box{align-self:center}'

    + '.prf-gate__box{position:relative;flex:0 0 auto;width:24px;height:24px;'
    + 'box-sizing:border-box;border-radius:2px;border:2px solid #7a7a7a;'
    + 'background:transparent;cursor:pointer;'
    + 'transition:background .12s linear,border-color .12s linear}'
    + '.prf-gate--light .prf-gate__box{background:#fff}'
    + '.prf-gate__box::before{content:"";position:absolute;inset:-6px}'

    + '.prf-gate--work .prf-gate__box{border-color:transparent;background:transparent}'
    + '.prf-gate--work .prf-gate__box::after{content:"";position:absolute;'
    + 'left:3px;top:3px;width:14px;height:14px;box-sizing:border-box;'
    + 'border-radius:50%;border:2px solid #4c4c4c;border-top-color:var(--prf-accent);'
    + 'animation:prf-spin .9s linear infinite}'
    + '.prf-gate--ok .prf-gate__box{background:var(--prf-ok);border-color:var(--prf-ok)}'
    + '.prf-gate--ok .prf-gate__box::after{content:"";position:absolute;'
    + 'left:6px;top:3px;width:5px;height:10px;'
    + 'border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}'
    + '.prf-gate--err .prf-gate__box{border-color:var(--prf-err)}'
    + '.prf-gate--err .prf-gate__box::after{content:"!";position:absolute;inset:0;'
    + 'display:flex;align-items:center;justify-content:center;'
    + 'color:var(--prf-err);font-weight:700;font-size:14px;line-height:1}'
    + '@keyframes prf-spin{to{transform:rotate(360deg)}}'

    + '.prf-gate__texts{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;gap:1px}'
    + '.prf-gate__text{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
    + 'font-size:13px;line-height:18px;height:18px;color:var(--prf-fg)}'
    + '.prf-gate--ok .prf-gate__text{font-weight:600}'
    + '.prf-gate__sub{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
    + 'font-size:10.5px;line-height:13px;height:13px;color:var(--prf-sub)}'
    + '.prf-gate__sub:empty{display:none}'

    + '.prf-gate__brandcol{flex:0 0 auto;margin-left:auto;display:flex;flex-direction:column;'
    + 'align-items:center;justify-content:center;gap:1px}'
    + '.prf-gate__brand{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;'
    + 'color:var(--prf-dim);font-size:11.5px;letter-spacing:1.35px;text-transform:uppercase;'
    + 'line-height:18px;height:18px;font-weight:600}'
    + '.prf-gate__brand img{display:block;width:18px;height:18px;object-fit:contain;opacity:.95}'
    + '.prf-gate--ok .prf-gate__brand{opacity:.85}'
    + '.prf-gate__links{display:flex;align-items:center;justify-content:center;gap:5px;'
    + 'white-space:nowrap;font-size:9px;line-height:13px;height:13px;color:var(--prf-dim)}'
    + '.prf-gate__links--with-logo{padding-left:24px}'   /* 19px 图标 + 6px 间距 */
    + '.prf-gate__links a{color:var(--prf-dim);text-decoration:none;'
    + 'border-bottom:1px dotted rgba(127,127,127,.5)}'
    + '.prf-gate__links a:hover{color:var(--prf-fg);border-bottom-color:currentColor}'
    + '.prf-gate__links .prf-sep{opacity:.55}'

    + '.prf-gate__bar{height:2px;margin-top:6px;background:#2c2c2c;overflow:hidden;display:none}'
    + '.prf-gate--light .prf-gate__bar{background:#e6e6e6}'
    + '.prf-gate--work .prf-gate__bar{display:block}'
    + '.prf-gate__fill{height:100%;width:0;background:var(--prf-accent);transition:width .2s linear}'

    + '.prf-gate__retry{flex:0 0 auto;border:1px solid #6a6a6a;border-radius:2px;'
    + 'padding:2px 8px;cursor:pointer;background:transparent;color:var(--prf-fg);'
    + 'font-size:11px;font-family:inherit;line-height:1.5}'
    + '.prf-gate__retry:hover{background:rgba(127,127,127,.18)}'

    + '.prf-gate--hidden{display:none!important}';

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    injectStyle.done = true;
    var s = document.createElement('style');
    s.id = STYLE_ID;
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  // ---------------------------------------------------------------- HTTP
  function postJSON(path, body) {
    return fetch(api(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        return { status: r.status, ok: r.ok, data: data };
      });
    });
  }

  var configPromise = null;
  function loadConfig() {
    if (!configPromise) {
      configPromise = new Promise(function (resolve) {
        var settled = false;
        var timer = setTimeout(function () {
          if (settled) return;
          settled = true;
          log('config 超时：拿不到 ' + api('/api/v1/config'));
          resolve({ __timeout: true });
        }, 8000);
        fetch(api('/api/v1/config'), { cache: 'no-store' })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            log('config ok', d);
            resolve(d || {});
          })
          .catch(function (err) {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            log('config 失败', err);
            resolve({ __error: true });
          });
      });
    }
    return configPromise;
  }

  // ---------------------------------------------------------------- PoW
  var workerUrl = api('/static/widget/pelareeflet-worker.js');

  function workerCount() {
    var n = (global.navigator && navigator.hardwareConcurrency) || 2;
    return Math.max(1, Math.min(4, n - 1 || 1));
  }


  // ---------------------------------------------------------------- 主线程兜底
  // 有些受限 webview（IDE 内置预览、某些小程序容器）会静默禁用 Web Worker：
  // 既不抛错也不回消息，表现就是永远转圈。这里留一份主线程实现作为兜底。
  var MT_K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ]);
  var MT_W = new Uint32Array(64);
  var MT_OUT = new Uint8Array(32);

  function mtSha256(bytes, len) {
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
        MT_W[i] = (bytes[j] << 24) | (bytes[j + 1] << 16) | (bytes[j + 2] << 8) | bytes[j + 3];
      }
      for (i = 16; i < 64; i++) {
        var w15 = MT_W[i - 15], w2 = MT_W[i - 2];
        var s0 = ((w15 >>> 7) | (w15 << 25)) ^ ((w15 >>> 18) | (w15 << 14)) ^ (w15 >>> 3);
        var s1 = ((w2 >>> 17) | (w2 << 15)) ^ ((w2 >>> 19) | (w2 << 13)) ^ (w2 >>> 10);
        MT_W[i] = (MT_W[i - 16] + s0 + MT_W[i - 7] + s1) | 0;
      }
      var a = H0, b = H1, c = H2, d = H3, e = H4, f = H5, g = H6, h = H7;
      for (i = 0; i < 64; i++) {
        var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
        var ch = (e & f) ^ (~e & g);
        var t1 = (h + S1 + ch + MT_K[i] + MT_W[i]) | 0;
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
      MT_OUT[k * 4] = (v >>> 24) & 0xff;
      MT_OUT[k * 4 + 1] = (v >>> 16) & 0xff;
      MT_OUT[k * 4 + 2] = (v >>> 8) & 0xff;
      MT_OUT[k * 4 + 3] = v & 0xff;
    }
    return MT_OUT;
  }

  function solveOnMainThread(job, onProgress) {
    return new Promise(function (resolve, reject) {
      var base = job.challenge + ':';
      var prefix = job.prefix | 0;
      var enc = new TextEncoder();
      var buf = new Uint8Array(256);
      var nonce = 0;
      var tried = 0;
      var total = Math.pow(16, prefix);
      var deadline = Date.now() + 45000;

      function tick() {
        var sliceEnd = Date.now() + 40;
        while (Date.now() < sliceEnd) {
          var bytes = enc.encode(base + nonce);
          buf.set(bytes);
          var out = mtSha256(buf, bytes.length);
          var ok = true;
          for (var i = 0; i < prefix; i++) {
            var nib = (i & 1) === 0 ? (out[i >> 1] >> 4) : (out[i >> 1] & 0x0f);
            if (nib !== 0) { ok = false; break; }
          }
          if (ok) { resolve(nonce); return; }
          nonce++;
          tried++;
        }
        onProgress(Math.min(0.99, tried / total));
        if (Date.now() > deadline) { reject(new Error('验证超时，请重试')); return; }
        setTimeout(tick, 0);
      }
      tick();
    });
  }

  function Solver(onProgress) {
    this.onProgress = onProgress || function () {};
    this.stopped = false;
    this.workers = [];
  }

  Solver.prototype.stop = function () {
    this.stopped = true;
    this.workers.forEach(function (w) { try { w.terminate(); } catch (e) {} });
    this.workers = [];
  };

  Solver.prototype.solveJob = function (job) {
    var self = this;
    self.stop();
    self.stopped = false;

    var n = workerCount();
    var tick = 0;

    return new Promise(function (resolve, reject) {
      var settled = false;
      var gotMessage = false;

      function finish(nonce) {
        if (settled) return;
        settled = true;
        self.stop();
        resolve(nonce);
      }

      function fail(err) {
        if (settled) return;
        settled = true;
        self.stop();
        reject(err);
      }

      function fallback(reason) {
        if (settled) return;
        log('主线程兜底：' + reason);
        self.stop();
        solveOnMainThread(job, self.onProgress).then(finish, fail);
      }

      for (var i = 0; i < n; i++) {
        (function (index) {
          var w;
          try {
            w = new Worker(workerUrl);
          } catch (e) {
            fallback('Worker 构造失败');
            return;
          }
          self.workers.push(w);
          w.onmessage = function (ev) {
            gotMessage = true;
            var m = ev.data || {};
            if (m.type === 'found') { finish(m.nonce); return; }
            if (m.type === 'error') { fail(new Error('验证失败，请重试')); return; }
            if (m.type === 'progress') {
              tick += m.tried || 0;
              self.onProgress(Math.min(0.99, tick / Math.pow(16, job.prefix || 4)));
            }
          };
          w.onerror = function () { fallback('Worker 加载失败'); };
          w.postMessage({
            challenge: job.challenge,
            prefix: job.prefix,
            start: index + Math.floor(Math.random() * 1000) * n,
            step: n
          });
        })(i);
      }

      // 2.5 秒内一个消息都没有 → 认定 Worker 被环境禁用，退回主线程
      setTimeout(function () {
        if (!settled && !gotMessage) fallback('Worker 无响应');
      }, 2500);

      setTimeout(function () {
        if (!settled) fail(new Error('验证超时，请重试'));
      }, 45000);
    });
  };

  // ---------------------------------------------------------------- 组件
  function render(mount, options) {
    if (typeof mount === 'string') mount = document.querySelector(mount);
    if (!mount) throw new Error('PelaReeflet: 挂载点不存在');
    if (mount.dataset.prfReady === '1') return mount._prfApi;

    injectStyle();
    options = options || {};

    var onSuccess = options.onSuccess || function () {};
    var onFail = options.onFail || function () {};
    // 主题：dark（默认）/ light / auto（跟随系统）；data-theme 优先于服务端配置
    var attrTheme = String(options.theme || mount.getAttribute('data-theme') || '').toLowerCase();
    var themeMode = attrTheme || 'dark';
    var stateCls = 'idle';
    var mql = global.matchMedia ? global.matchMedia('(prefers-color-scheme: light)') : null;

    function resolveTheme() {
      if (themeMode === 'auto') return (mql && mql.matches) ? 'light' : 'dark';
      return themeMode === 'light' ? 'light' : 'dark';
    }

    var theme = resolveTheme();

    var root = document.createElement('div');
    root.className = 'prf-gate prf-gate--idle' + (theme === 'light' ? ' prf-gate--light' : '');
    root.setAttribute('role', 'checkbox');
    root.setAttribute('aria-checked', 'false');
    root.setAttribute('tabindex', '0');
    root.setAttribute('aria-label', '人机验证');
    root.innerHTML = ''
      + '<div class="prf-gate__slot">'
      + '  <div class="prf-gate__row">'
      + '    <span class="prf-gate__box"></span>'
      + '    <span class="prf-gate__texts">'
      + '      <span class="prf-gate__text"></span>'
      + '      <span class="prf-gate__sub"></span>'
      + '    </span>'
      + '    <span class="prf-gate__brandcol">'
      + '      <span class="prf-gate__brand"></span>'
      + '      <span class="prf-gate__links"></span>'
      + '    </span>'
      + '  </div>'
      + '  <div class="prf-gate__bar"><div class="prf-gate__fill"></div></div>'
      + '</div>';

    mount.innerHTML = '';
    mount.appendChild(root);
    mount.dataset.prfReady = '1';

    var boxEl = root.querySelector('.prf-gate__box');
    var textEl = root.querySelector('.prf-gate__text');
    var subEl = root.querySelector('.prf-gate__sub');
    var fillEl = root.querySelector('.prf-gate__fill');
    var rowEl = root.querySelector('.prf-gate__row');

    var cfg = {};
    var ticket = '';
    var destroyed = false;
    var busy = false;
    var samples = [];
    var lastMoveAt = 0;
    var downAt = 0;
    var downType = '';
    var refreshTimer = null;
    var flowTimer = null;

    function setSub(sub) {
      subEl.textContent = sub || '';
    }

    function applyClass() {
      root.className = 'prf-gate prf-gate--' + stateCls
        + (theme === 'light' ? ' prf-gate--light' : '');
    }

    function setState(cls, main, sub) {
      stateCls = cls;
      applyClass();
      textEl.textContent = main;
      subEl.textContent = sub || '';
      root.setAttribute('aria-checked', cls === 'ok' ? 'true' : 'false');
    }

    if (mql && mql.addEventListener) {
      mql.addEventListener('change', function () {
        if (themeMode !== 'auto') return;
        theme = resolveTheme();
        applyClass();
      });
    }

    function paintBrand(c) {
      var brand = root.querySelector('.prf-gate__brand');
      if (c.attribution === false) { brand.remove(); return; }
      var logo = String(c.logo || '').trim();
      if (logo) {
        var img = document.createElement('img');
        img.src = /^https?:/i.test(logo) ? logo : ORIGIN + logo;
        img.alt = '';
        img.decoding = 'async';
        img.onerror = function () { img.remove(); };
        brand.appendChild(img);
        var linksEl = root.querySelector('.prf-gate__links');
        if (linksEl) linksEl.classList.add('prf-gate__links--with-logo');
      }
      var text = document.createElement('span');
      text.className = 'prf-gate__brand-text';
      text.textContent = c.brand || 'PELAGIC BEACON';
      brand.appendChild(text);
    }

    function paintFoot(c) {
      var foot = root.querySelector('.prf-gate__links');
      var links = c.links || {};
      var items = [
        ['开源协议', links.license],
        ['关于我们', links.about]
      ].filter(function (it) { return it[1]; });

      items.forEach(function (it, i) {
        if (i) {
          var sep = document.createElement('span');
          sep.className = 'prf-sep';
          sep.textContent = '·';
          foot.appendChild(sep);
        }
        var a = document.createElement('a');
        a.href = it[1];
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = it[0];
        foot.appendChild(a);
      });
      if (!items.length) foot.remove();
    }

    function showRetry() {
      if (rowEl.querySelector('.prf-gate__retry')) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'prf-gate__retry';
      btn.textContent = '重试';
      btn.onclick = function (ev) {
        if (ev && ev.stopPropagation) ev.stopPropagation();
        btn.remove();
        reset();
      };
      rowEl.appendChild(btn);
    }

    function prefetch() {
      return fetch(api('/api/v1/challenge'), { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || !d.ok) throw new Error(d && d.message ? d.message : '验证服务暂时不可用');
          return d;
        });
    }

    var jobPromise = null;

    function ensureJob() {
      if (!jobPromise) {
        jobPromise = prefetch();
        jobPromise.catch(function () { jobPromise = null; });
      }
      return jobPromise;
    }

    function succeed(t, ttl) {
      if (flowTimer) { clearTimeout(flowTimer); flowTimer = null; }
      log('验证通过');
      ticket = t;
      onSuccess(ticket);
      setState('ok', '验证通过', '已完成安全验证');
      scheduleRefresh(ttl);
      try {
        mount.dispatchEvent(new CustomEvent('pelareeflet:success', {
          bubbles: true, detail: { ticket: t }
        }));
      } catch (e) {}
    }

    function scheduleRefresh(ttl) {
      if (refreshTimer) clearTimeout(refreshTimer);
      var wait = Math.max(30000, (ttl || 300) * 1000 - 30000);
      refreshTimer = setTimeout(function () {
        if (destroyed || !ticket) return;
        ticket = '';
        setIdle();
      }, wait);
    }

    function failed(err) {
      if (flowTimer) { clearTimeout(flowTimer); flowTimer = null; }
      log('验证失败', err && err.message);
      ticket = '';
      var msg = (err && err.message) || '验证失败，请重试';
      onFail(msg);
      setState('err', msg, '');
      fillEl.style.width = '0%';
      showRetry();
      jobPromise = null;
    }

    function setIdle() {
      ticket = '';
      setState('idle', '请点击完成验证', '点击左侧方框开始');
      fillEl.style.width = '0%';
      jobPromise = null;
      ensureJob();
    }

    function runFlow(info, quiet) {
      if (destroyed || busy) return;
      busy = true;
      log('开始验证', { click: cfg.click, pointer: info.pointer_type });

      // 整条链路的总看门狗：任何一步卡住都不会无限转圈
      if (flowTimer) clearTimeout(flowTimer);
      flowTimer = setTimeout(function () {
        if (!busy) return;
        busy = false;
        failed(new Error('验证超时，请重试'));
      }, 45000);

      if (!quiet) {
        setState('work', '正在验证…', '请稍候');
        fillEl.style.width = '0%';
      }

      ensureJob()
        .then(function (job) {
          if (destroyed) throw new Error('stale');
          log('拿到挑战', { prefix: job.prefix });
          if (cfg.click === false) {
            return { job: job, gate: '' };
          }
          setSub('② 核对交互…');
          return postJSON('/api/v1/check', {
            token: job.token,
            path: info.path,
            pointer_type: info.pointer_type,
            hold_ms: info.hold_ms,
            features: info.features
          }).then(function (res) {
            if (!res.ok || !res.data || !res.data.ok) {
              throw new Error((res.data && res.data.message) || '验证未通过，请重试');
            }
            log('点击关卡通过');
            setSub('③ 计算中 0%');
            return { job: job, gate: res.data.gate };
          });
        })
        .then(function (x) {
          if (destroyed) throw new Error('stale');
          return new Solver(function (p) {
            fillEl.style.width = (p * 100).toFixed(1) + '%';
            setSub('③ 计算中 ' + Math.round(p * 100) + '%');
          }).solveJob(x.job).then(function (nonce) {
            return { job: x.job, nonce: nonce, gate: x.gate };
          });
        })
        .then(function (x) {
          if (destroyed) throw new Error('stale');
          return postJSON('/api/v1/solve', {
            token: x.job.token, nonce: x.nonce, gate: x.gate
          });
        })
        .then(function (res) {
          if (destroyed) return;
          log('提交答案', res.status, res.data);
          if (res.ok && res.data && res.data.ok && res.data.ticket) {
            succeed(res.data.ticket, res.data.ttl);
            return;
          }
          throw new Error((res.data && res.data.message) || '验证未通过，请重试');
        })
        .catch(function (err) {
          if (destroyed || (err && err.message === 'stale')) return;
          failed(err);
        })
        .then(function () { busy = false; });
    }

    // -------------------------------------------------- 交互采集
    function onMove(ev) {
      var now = Date.now();
      if (now - lastMoveAt < 25) return;
      lastMoveAt = now;
      samples.push([Math.round(ev.clientX), Math.round(ev.clientY), now]);
      if (samples.length > 200) samples.shift();
    }

    function collectFeatures() {
      var nav = global.navigator || {};
      var uaData = nav.userAgentData || null;
      var ua = String(nav.userAgent || '');
      return {
        // 自报身份
        webdriver: nav.webdriver === true,
        headless_ua: /HeadlessChrome/i.test(ua),
        ua: ua.slice(0, 200),
        // 环境自洽性：无头环境通常这里全是「空」
        chrome: typeof global.chrome !== 'undefined',
        plugins: (nav.plugins && nav.plugins.length) || 0,
        languages: (nav.languages || []).length,
        hardware: nav.hardwareConcurrency || 0,
        depth: (global.screen && global.screen.colorDepth) || 0,
        screen_w: (global.screen && global.screen.width) || 0,
        dpr: global.devicePixelRatio || 0,
        touch: ('ontouchstart' in global) ? 1 : 0,
        platform: uaData ? String(uaData.platform || '').slice(0, 60) : '',
        mobile: !!(uaData && uaData.mobile)
      };
    }

    function activate(ev) {
      if (busy || ticket) return;
      var hold = downAt ? Math.max(0, Date.now() - downAt) : 60;
      var trusted = !ev || ev.isTrusted !== false;
      runFlow({
        path: samples.slice(),
        pointer_type: trusted ? (downType || 'mouse') : 'synthetic',
        hold_ms: hold,
        features: collectFeatures()
      });
    }

    function onKey(ev) {
      if (ev.key !== ' ' && ev.key !== 'Enter' && ev.key !== 'Spacebar') return;
      ev.preventDefault();
      if (busy || ticket) return;
      runFlow({ path: [], pointer_type: 'key', hold_ms: 80, features: collectFeatures() });
    }

    function reset() {
      if (destroyed) return;
      if (refreshTimer) { clearTimeout(refreshTimer); refreshTimer = null; }
      busy = false;
      samples = [];
      jobPromise = null;
      var btn = rowEl.querySelector('.prf-gate__retry');
      if (btn) btn.remove();
      setIdle();
    }

    document.addEventListener('mousemove', onMove, { passive: true });
    if (global.PointerEvent) {
      boxEl.addEventListener('pointerdown', function (ev) {
        downAt = Date.now();
        downType = ev.pointerType || 'mouse';
      });
    } else {
      boxEl.addEventListener('mousedown', function () {
        downAt = Date.now(); downType = 'mouse';
      });
      boxEl.addEventListener('touchstart', function () {
        downAt = Date.now(); downType = 'touch';
      }, { passive: true });
    }
    boxEl.addEventListener('click', activate);
    root.addEventListener('keydown', onKey);

    // 注意：不能叫 api —— 那会遮蔽模块级的 api(path)，prefetch 里就调不到了
    var instanceApi = {
      reset: reset,
      getToken: function () { return ticket; },
      destroy: function () {
        destroyed = true;
        if (refreshTimer) clearTimeout(refreshTimer);
        document.removeEventListener('mousemove', onMove);
        root.removeEventListener('keydown', onKey);
        mount.innerHTML = '';
        delete mount.dataset.prfReady;
      }
    };
    mount._prfApi = instanceApi;

    setState('idle', '加载中…', '');

    loadConfig().then(function (c) {
      cfg = c || {};
      if (!attrTheme && c.theme) {
        themeMode = String(c.theme).toLowerCase();
        theme = resolveTheme();
        applyClass();
      }
      paintBrand(c);
      paintFoot(c);
      if (c.__timeout || c.__error) {
        setState('err', '无法连接验证服务', '请检查网络后刷新页面');
        return;
      }
      if (c.enabled === false) {
        setState('err', '验证服务未就绪', '请联系站点管理员');
        return;
      }
      setIdle();
    });

    return instanceApi;
  }

  // ---------------------------------------------------------------- 自动挂载
  function autoMount() {
    var nodes = document.querySelectorAll('.pelareeflet, [data-pelareeflet]');
    for (var i = 0; i < nodes.length; i++) {
      (function (node) {
        if (node.dataset.prfReady === '1') return;
        var name = node.getAttribute('data-callback');
        var cb = name && global[name] ? global[name] : null;
        render(node, {
          theme: node.getAttribute('data-theme') || '',
          onSuccess: function (ticket) {
            var field = node.getAttribute('data-response-field');
            if (field) {
              var input = document.querySelector('input[name="' + field + '"]');
              if (input) input.value = ticket;
            }
            if (typeof cb === 'function') cb(ticket);
          }
        });
      })(nodes[i]);
    }
  }

  global.PelaReeflet = {
    render: render,
    version: '1.0.0',
    origin: ORIGIN,
    ready: function (cb) {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', cb);
      } else {
        setTimeout(cb, 0);
      }
    }
  };

  global.PelaReeflet.ready(autoMount);
})(window);
