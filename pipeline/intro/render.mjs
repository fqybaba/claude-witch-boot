// 把 intro.html 逐帧渲染成 PNG。不依赖 playwright 包：直接用 Playwright 装好的 headless Chromium，走 DevTools 协议。
// 用法：node render.mjs <intro|loop> <输出目录> [--page intro.html] [--fps 30] [--from 秒] [--to 秒] [--char 人物帧目录] [--char-start 秒]
//   --char：Seedance 视频拆出来的帧（0001.jpg…），从 --char-start 秒开始按 30fps 对应到人物图层；不给就用定妆图静图
import { spawn } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');            // 项目根目录，用 http 提供，避免 file:// 让画布被“污染”
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const mode = args[0], out = path.resolve(args[1]);
const fps = +opt('--fps', 30);
const page = opt('--page', 'intro.html');
const charDir = opt('--char', null), charStart = +opt('--char-start', 5.8), charFps = +opt('--char-fps', 30);
fs.mkdirSync(out, { recursive: true });

const types = { '.html': 'text/html; charset=utf-8', '.png': 'image/png', '.jpg': 'image/jpeg', '.js': 'text/javascript' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': types[path.extname(p).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;

const pw = path.join(process.env.LOCALAPPDATA, 'ms-playwright');
const shellDir = fs.readdirSync(pw).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
const exe = path.join(pw, shellDir, 'chrome-headless-shell-win64', 'chrome-headless-shell.exe');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'intro-render-'));
const chrome = spawn(exe, ['--remote-debugging-port=0', `--user-data-dir=${profile}`, '--hide-scrollbars',
  '--force-color-profile=srgb', '--disable-gpu-vsync', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
const wsUrl = await new Promise((res, rej) => {
  let buf = '';
  chrome.stderr.on('data', d => { buf += d; const m = buf.match(/DevTools listening on (ws:\S+)/); if (m) res(m[1]); });
  setTimeout(() => rej(new Error('Chromium 没有启动：' + buf)), 20000);
});

const ws = new WebSocket(wsUrl);
await new Promise(r => ws.addEventListener('open', r));
let id = 0; const pending = new Map();
ws.addEventListener('message', e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
});
const send = (method, params = {}, sessionId) => new Promise((res, rej) => {
  const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params, sessionId }));
});
const { targetId } = await send('Target.createTarget', { url: 'about:blank', width: 1920, height: 1080 });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
const S = (m, p) => send(m, p, sessionId);
const evaluate = async expr => {
  const r = await S('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
};
await S('Page.enable');
await S("Page.navigate", { url: `${base}/${path.relative(root, here).split(path.sep).join("/")}/${page}` });
for (let i = 0; i < 100 && !(await evaluate('typeof window.ready === "function"').catch(() => false)); i++) await new Promise(r => setTimeout(r, 100));
await evaluate('window.ready()');

const len = mode === 'loop' ? await evaluate('LOOP_LEN') : await evaluate('INTRO_LEN');
const from = +opt('--from', 0), to = +opt('--to', len);
const charFrames = charDir ? fs.readdirSync(charDir).filter(f => /\.(jpg|png)$/i.test(f)).sort() : [];
const relChar = charDir ? path.relative(root, path.resolve(charDir)).split(path.sep).join('/') : '';
const n = Math.round((to - from) * fps);
const t0 = Date.now();
for (let i = 0; i < n; i++) {
  const t = from + i / fps;
  let url = '';
  if (charFrames.length && mode === 'intro' && t >= charStart) {
    const k = Math.min(charFrames.length - 1, Math.floor((t - charStart) * charFps));
    url = `/${relChar}/${charFrames[k]}`;
  }
  const data = await evaluate(`setChar(${JSON.stringify(url)}).then(() => { render(${t}, ${JSON.stringify(mode)}); return document.getElementById('c').toDataURL('image/png'); })`);
  fs.writeFileSync(path.join(out, String(Math.round(t * fps)).padStart(4, '0') + '.png'), Buffer.from(data.split(',')[1], 'base64'));
  if (i % 30 === 0) process.stdout.write(`\r${i}/${n} 帧  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
console.log(`\r完成 ${n} 帧 → ${out}  用时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);
ws.close(); chrome.kill(); server.close();
try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
