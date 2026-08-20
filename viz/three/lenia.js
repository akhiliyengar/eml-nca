/**
 * Lenia on the GPU, with a switchable growth function.
 *
 * The scientific point of this page is one comparison:
 *
 *   Gaussian growth   G(u) = 2*exp(-(u-mu)^2 / (2 sigma^2)) - 1     (control)
 *   Erez EML gate     G(x) = (c+x)^a - b*x - c^a                    (treatment)
 *
 * Erez (arXiv:2605.02972) shows the second is non-monotone in a SINGLE
 * 3-parameter block, where a Gaussian or Hill needs a difference of two opposed
 * blocks. Lenia's growth function is univariate and non-monotone, so it is the
 * one place in this project where that result maps directly onto the target.
 *
 * Ping-pong framebuffers: cellular automata are the natural GPU workload --
 * every cell reads its neighbourhood and writes itself, with no cross-cell
 * dependency within a step. Two textures alternate as read and write targets
 * because a texture cannot be sampled and rendered to in the same pass.
 *
 * Deliberately dependency-free: raw WebGL2, no three.js runtime download, no
 * build step. `python -m http.server` in this directory is the whole toolchain.
 */

const N = 256;                      // simulation grid (square, power of two)
const canvas = document.getElementById('c');
const gl = canvas.getContext('webgl2', { antialias: false, alpha: false });
if (!gl) {
  document.getElementById('stage').innerHTML =
    '<p style="color:#fc8181">WebGL2 unavailable in this browser.</p>';
  throw new Error('no webgl2');
}
gl.getExtension('EXT_color_buffer_float');

/* ------------------------------------------------------------------ shaders */

const VERT = `#version 300 es
in vec2 p;
out vec2 uv;
void main() { uv = p * 0.5 + 0.5; gl_Position = vec4(p, 0.0, 1.0); }`;

/**
 * One Lenia step.
 *
 *   potential U(x) = sum_neighbourhood K(r) * A(x + dr)      (normalised)
 *   A(t+1)         = clamp(A + dt * G(U), 0, 1)
 *
 * The kernel is a Gaussian ring: a shell at mid-radius rather than a blob. That
 * shape is what produces gliders instead of blobs -- it makes a cell care about
 * neighbours at a preferred DISTANCE, which is the continuous analogue of
 * Conway's "exactly 2 or 3 neighbours".
 */
const STEP = `#version 300 es
precision highp float;
in vec2 uv;
out vec4 outColor;

uniform sampler2D uState;
uniform float uN, uR, uDt;
uniform int   uMode;        // 0 = gaussian control, 1 = erez EML gate
uniform float uMu, uSigma;                  // gaussian
uniform float uA, uB, uC, uScale;           // erez gate

float kernel(float r) {                     // Gaussian ring, peak at r = 0.5
  float x = (r - 0.5) / 0.15;
  return exp(-0.5 * x * x);
}

// Control. Standard Lenia growth: a bump in [-1, 1], monotone on each side of
// its peak but symmetric -- it cannot express activation-then-suppression with
// independent slopes.
float growthGaussian(float u) {
  float x = (u - uMu) / uSigma;
  return 2.0 * exp(-0.5 * x * x) - 1.0;
}

// Treatment. Erez's centered activation-suppression gate, arXiv:2605.02972 eq 6.
// Rises as (c+x)^a, then the -b*x term takes over: one block, one optimum at
// R* = (a/b)^(1/(1-a)). The -c^a term fixes G(0) = 0 so the quiescent state
// stays quiescent, which matters because Lenia adds dt*G every step and a
// nonzero baseline would inflate the whole field.
float growthErez(float x) {
  float base = max(uC + x, 0.0);
  float g = pow(base, uA) - uB * x - pow(max(uC, 1e-6), uA);
  return clamp(uScale * g, -1.0, 1.0);
}

void main() {
  float r = uR;
  float sum = 0.0, wsum = 0.0;
  // Square window over the disc of radius r; contributions outside are zero.
  for (int dy = -24; dy <= 24; dy++) {
    if (float(abs(dy)) > r) continue;
    for (int dx = -24; dx <= 24; dx++) {
      float d = length(vec2(float(dx), float(dy)));
      if (d > r || d < 1e-6) continue;
      float w = kernel(d / r);
      vec2 o = vec2(float(dx), float(dy)) / uN;
      sum  += w * texture(uState, fract(uv + o)).r;   // fract => periodic
      wsum += w;
    }
  }
  float u = wsum > 0.0 ? sum / wsum : 0.0;
  float g = (uMode == 0) ? growthGaussian(u) : growthErez(u);
  float a = texture(uState, uv).r;
  outColor = vec4(clamp(a + uDt * g, 0.0, 1.0), 0.0, 0.0, 1.0);
}`;

/** Display pass: scalar field -> a legible ramp. */
const SHOW = `#version 300 es
precision highp float;
in vec2 uv;
out vec4 outColor;
uniform sampler2D uState;
void main() {
  float a = texture(uState, uv).r;
  vec3 col = vec3(0.04, 0.05, 0.08)
           + vec3(0.10, 0.75, 0.72) * a
           + vec3(0.85, 0.60, 0.10) * pow(a, 6.0);
  outColor = vec4(col, 1.0);
}`;

/* ------------------------------------------------------------------- plumbing */

function compile(type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(s));
  }
  return s;
}
function program(fragSrc) {
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl.VERTEX_SHADER, VERT));
  gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fragSrc));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(p));
  }
  return p;
}

const progStep = program(STEP);
const progShow = program(SHOW);

const quad = gl.createVertexArray();
gl.bindVertexArray(quad);
const buf = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buf);
gl.bufferData(gl.ARRAY_BUFFER,
  new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
gl.enableVertexAttribArray(0);
gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

function makeTarget() {
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.R32F, N, N, 0, gl.RED, gl.FLOAT, null);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
  const fbo = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0,
                          gl.TEXTURE_2D, tex, 0);
  return { tex, fbo };
}
let A = makeTarget(), B = makeTarget();

/* ------------------------------------------------------------------ seeding */

function upload(data) {
  for (const t of [A, B]) {
    gl.bindTexture(gl.TEXTURE_2D, t.tex);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, N, N, gl.RED, gl.FLOAT, data);
  }
  step = 0; massHist = [];
}

/**
 * Orbium-like glider seed.
 *
 * Parameters are NOT arbitrary -- they were found by simulating candidates in
 * NumPy and keeping one that survives 400+ steps. The first attempt used
 * Rs=26, amp=1.15 and died instantly: its mean potential was 0.49 against
 * mu=0.15, so the Gaussian growth function returned about -1 everywhere.
 *
 * The survival basin is razor-thin, which matters more than the specific
 * numbers. Measured on a 128 grid with kernel R=13, mu=0.15, sigma=0.017:
 *
 *   Rs=8   amp=0.50  -> DIED at step 22
 *   Rs=8   amp=0.60  -> ALIVE at 400, mass 3.5e-03   <- used here
 *   Rs=10  amp=any   -> DIED, every variant tried
 *   Rs=13  amp=0.50  -> ALIVE but mass 2.1e-01, i.e. it grew to fill
 *
 * A one-pixel change in radius flips the outcome. Rung 2 must therefore sweep
 * rather than test a single configuration: "the EML gate killed Orbium" would
 * otherwise be indistinguishable from "that particular seed was outside the
 * basin for any growth function".
 */
function seedOrbium() {
  const d = new Float32Array(N * N);
  const cx = N / 2, cy = N / 2;
  const Rs = 8, amp = 0.60, shell = 0.55, width = 0.28;
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      const r = Math.hypot(x - cx, y - cy) / Rs;
      if (r < 1.0) {
        d[y * N + x] = amp * Math.exp(-Math.pow((r - shell) / width, 2));
      }
    }
  }
  upload(d);
}
function seedBlob() {
  const d = new Float32Array(N * N);
  const cx = N / 2, cy = N / 2, R = 18;
  for (let y = 0; y < N; y++)
    for (let x = 0; x < N; x++) {
      const r = Math.hypot(x - cx, y - cy) / R;
      if (r < 1) d[y * N + x] = 1 - r * r;
    }
  upload(d);
}
function seedNoise() {
  // Deterministic LCG rather than Math.random: determinism is an invariant in
  // this project, and a viewer you cannot reproduce is a viewer you cannot cite.
  const d = new Float32Array(N * N);
  let s = 12345;
  for (let i = 0; i < d.length; i++) {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    d[i] = (s / 0x7fffffff) < 0.30 ? (s % 1000) / 1000 : 0;
  }
  upload(d);
}

/* --------------------------------------------------------------------- UI */

const el = (id) => document.getElementById(id);
const ui = {
  mode: 0, mu: 0.15, sigma: 0.017,
  a: 0.5, b: 0.3, c: 0.02, scale: 1.0,
  R: 13, dt: 0.10, paused: false,
};

function erezPeak(a, b) {
  if (a <= 0 || a >= 1 || b <= 0) return NaN;
  return Math.pow(a / b, 1 / (1 - a));
}

function bind(id, key, fmt, out) {
  const s = el(id);
  const show = () => { el(out).textContent = fmt(ui[key]); };
  s.addEventListener('input', () => { ui[key] = parseFloat(s.value); show(); refresh(); });
  show();
}
const f2 = (x) => x.toFixed(2), f3 = (x) => x.toFixed(3), f0 = (x) => String(x | 0);

bind('mu', 'mu', f3, 'vmu');       bind('sig', 'sigma', f3, 'vsig');
bind('a', 'a', f3, 'va');          bind('b', 'b', f3, 'vb');
bind('c', 'c', f3, 'vc');          bind('gscale', 'scale', f2, 'vs');
bind('R', 'R', f0, 'vR');          bind('dt', 'dt', f2, 'vdt');

function refresh() {
  const p = erezPeak(ui.a, ui.b);
  el('peak').textContent = isNaN(p) ? 'not unimodal (needs 0<a<1, b>0)' : p.toFixed(4);
}
function setMode(m) {
  ui.mode = m;
  el('bGauss').classList.toggle('on', m === 0);
  el('bErez').classList.toggle('on', m === 1);
  el('fsGauss').style.display = m === 0 ? '' : 'none';
  el('fsErez').style.display = m === 1 ? '' : 'none';
  el('gdesc').textContent = m === 0
    ? 'Control. Symmetric bump; cannot give activation and suppression independent slopes.'
    : 'Treatment. One 3-parameter block, non-monotone. A Hill or Gaussian needs two opposed blocks.';
  massHist = [];
}
el('bGauss').onclick = () => setMode(0);
el('bErez').onclick = () => setMode(1);
el('bOrbium').onclick = seedOrbium;
el('bBlob').onclick = seedBlob;
el('bNoise').onclick = seedNoise;
el('bPause').onclick = () => {
  ui.paused = !ui.paused;
  el('bPause').textContent = ui.paused ? 'resume' : 'pause';
  el('bPause').classList.toggle('on', ui.paused);
};

/* ------------------------------------------------------------------- loop */

let step = 0;
let massHist = [];
const readback = new Float32Array(N * N);

function simulate() {
  gl.useProgram(progStep);
  gl.bindFramebuffer(gl.FRAMEBUFFER, B.fbo);
  gl.viewport(0, 0, N, N);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, A.tex);

  const u = (n) => gl.getUniformLocation(progStep, n);
  gl.uniform1i(u('uState'), 0);
  gl.uniform1f(u('uN'), N);
  gl.uniform1f(u('uR'), ui.R);
  gl.uniform1f(u('uDt'), ui.dt);
  gl.uniform1i(u('uMode'), ui.mode);
  gl.uniform1f(u('uMu'), ui.mu);
  gl.uniform1f(u('uSigma'), ui.sigma);
  gl.uniform1f(u('uA'), ui.a);
  gl.uniform1f(u('uB'), ui.b);
  gl.uniform1f(u('uC'), ui.c);
  gl.uniform1f(u('uScale'), ui.scale);

  gl.bindVertexArray(quad);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  [A, B] = [B, A];
  step++;
}

function measure() {
  // Total mass is the survival signal: a pattern that dies goes to 0, one that
  // runs away saturates the grid. Read back sparingly -- glReadPixels stalls
  // the pipeline, so once every 15 steps rather than every step.
  gl.bindFramebuffer(gl.FRAMEBUFFER, A.fbo);
  gl.readPixels(0, 0, N, N, gl.RED, gl.FLOAT, readback);
  let m = 0;
  for (let i = 0; i < readback.length; i++) m += readback[i];
  m /= readback.length;
  massHist.push(m);
  if (massHist.length > 40) massHist.shift();

  let gain = NaN;
  if (massHist.length > 8) {
    const prev = massHist[massHist.length - 9];
    if (prev > 1e-9) gain = Math.pow(m / prev, 1 / 8);
  }

  el('rstep').textContent = step;
  el('rmass').textContent = m.toExponential(3);

  const g = el('rgain'), vd = el('rverdict');
  if (!isFinite(gain)) { g.textContent = '—'; }
  else {
    g.textContent = gain.toFixed(5);
    g.className = 'v ' + (Math.abs(gain - 1) < 0.002 ? 'ok'
                        : Math.abs(gain - 1) < 0.02 ? 'warn' : 'bad');
  }
  if (m < 1e-6) { vd.textContent = 'DIED'; vd.className = 'v bad'; }
  else if (m > 0.55) { vd.textContent = 'SATURATED'; vd.className = 'v bad'; }
  else if (isFinite(gain) && Math.abs(gain - 1) < 0.002) {
    vd.textContent = 'persisting'; vd.className = 'v ok';
  } else { vd.textContent = 'transient'; vd.className = 'v warn'; }
}

function draw() {
  gl.useProgram(progShow);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, A.tex);
  gl.uniform1i(gl.getUniformLocation(progShow, 'uState'), 0);
  gl.bindVertexArray(quad);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
}

function frame() {
  if (!ui.paused) {
    for (let i = 0; i < 2; i++) simulate();
    if (step % 15 === 0) measure();
  }
  draw();
  requestAnimationFrame(frame);
}

canvas.width = canvas.height = 512;
setMode(0);
refresh();
seedOrbium();
frame();
