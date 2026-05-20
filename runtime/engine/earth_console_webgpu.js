/**
 * Earth Console — WebGPU instanced agent sprites (lite 2D mode).
 * Falls back silently; caller keeps canvas2d path.
 */
(function (global) {
  const CULTURE_RGB = [
    [0.498, 0.851, 0.604],
    [0.910, 0.722, 0.427],
    [0.431, 0.710, 1.0],
    [0.788, 0.627, 0.863],
    [0.941, 0.443, 0.471],
    [0.239, 0.839, 0.776],
    [0.659, 0.831, 1.0],
    [0.831, 0.647, 0.455],
  ];

  const WGSL = `
struct Uniforms {
  viewport: vec2f,
  pad: vec2f,
};
@group(0) @binding(0) var<uniform> u: Uniforms;
struct Instance {
  @location(0) pos: vec2f,
  @location(1) color: vec3f,
  @location(2) radius: f32,
  @location(3) selected: f32,
};
struct VsOut {
  @builtin(position) pos: vec4f,
  @location(0) color: vec3f,
  @location(1) selected: f32,
  @location(2) uv: vec2f,
};
@vertex fn vs_main(
  @builtin(vertex_index) vi: u32,
  inst: Instance,
) -> VsOut {
  let corners = array<vec2f, 6>(
    vec2f(-1.0, -1.0), vec2f(1.0, -1.0), vec2f(-1.0, 1.0),
    vec2f(1.0, -1.0), vec2f(1.0, 1.0), vec2f(-1.0, 1.0),
  );
  let c = corners[vi];
  let r = inst.radius * (1.0 + 0.35 * inst.selected);
  let clip = vec2f(
    (inst.pos.x + c.x * r) / u.viewport.x * 2.0 - 1.0,
    1.0 - (inst.pos.y + c.y * r) / u.viewport.y * 2.0,
  );
  var o: VsOut;
  o.pos = vec4f(clip, 0.0, 1.0);
  o.color = inst.color;
  o.selected = inst.selected;
  o.uv = c;
  return o;
}
@fragment fn fs_main(in: VsOut) -> @location(0) vec4f {
  let d = length(in.uv);
  if (d > 1.0) { discard; }
  let glow = 1.0 - smoothstep(0.55, 1.0, d);
  let core = 1.0 - smoothstep(0.0, 0.45, d);
  var col = in.color * (0.35 * glow + 0.65 * core);
  if (in.selected > 0.5) {
    col = mix(col, vec3f(0.24, 0.84, 0.78), 0.35);
  }
  let alpha = glow * 0.92;
  return vec4f(col, alpha);
}
`;

  class EarthConsoleWebGPU {
    constructor(canvas) {
      this.canvas = canvas;
      this.device = null;
      this.pipeline = null;
      this.uniformBuf = null;
      this.instanceBuf = null;
      this.bindGroup = null;
      this.capacity = 0;
      this.ready = false;
    }

    async init() {
      if (!this.canvas || !navigator.gpu) return false;
      const adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
      if (!adapter) return false;
      this.device = await adapter.requestDevice();
      const ctx = this.canvas.getContext('webgpu');
      const format = navigator.gpu.getPreferredCanvasFormat();
      ctx.configure({ device: this.device, format, alphaMode: 'premultiplied' });
      this.ctx = ctx;
      this.format = format;
      const mod = this.device.createShaderModule({ code: WGSL });
      const layout = this.device.createBindGroupLayout({
        entries: [{ binding: 0, visibility: GPUShaderStage.VERTEX, buffer: { type: 'uniform' } }],
      });
      const plLayout = this.device.createPipelineLayout({ bindGroupLayouts: [layout] });
      this.pipeline = this.device.createRenderPipeline({
        layout: plLayout,
        vertex: {
          module: mod,
          entryPoint: 'vs_main',
          buffers: [{
            arrayStride: 32,
            stepMode: 'instance',
            attributes: [
              { shaderLocation: 0, offset: 0, format: 'float32x2' },
              { shaderLocation: 1, offset: 8, format: 'float32x3' },
              { shaderLocation: 2, offset: 20, format: 'float32' },
              { shaderLocation: 3, offset: 24, format: 'float32' },
            ],
          }],
        },
        fragment: {
          module: mod,
          entryPoint: 'fs_main',
          targets: [{ format, blend: {
            color: { srcFactor: 'src-alpha', dstFactor: 'one-minus-src-alpha' },
            alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha' },
          } }],
        },
        primitive: { topology: 'triangle-list' },
      });
      this.uniformBuf = this.device.createBuffer({
        size: 16,
        usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
      });
      this.bindGroup = this.device.createBindGroup({
        layout,
        entries: [{ binding: 0, resource: { buffer: this.uniformBuf } }],
      });
      this.ready = true;
      return true;
    }

    resize(w, h) {
      if (!this.ready) return;
      this.canvas.width = w;
      this.canvas.height = h;
      this.ctx.configure({
        device: this.device,
        format: this.format,
        alphaMode: 'premultiplied',
      });
      const data = new Float32Array([w, h, 0, 0]);
      this.device.queue.writeBuffer(this.uniformBuf, 0, data);
    }

    _ensureCapacity(n) {
      const need = Math.max(n, 64);
      if (this.instanceBuf && this.capacity >= need) return;
      if (this.instanceBuf) this.instanceBuf.destroy();
      this.capacity = need;
      this.instanceBuf = this.device.createBuffer({
        size: need * 32,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
      });
    }

    /**
     * @param {Array} agents screen-space agents {sx, sy, culture, selected}
     */
    drawInstances(agents) {
      if (!this.ready || !agents.length) return false;
      const n = agents.length;
      this._ensureCapacity(n);
      const data = new Float32Array(n * 8);
      for (let i = 0; i < n; i++) {
        const a = agents[i];
        const c = CULTURE_RGB[(a.culture ?? 0) % CULTURE_RGB.length];
        const base = i * 8;
        data[base] = a.sx;
        data[base + 1] = a.sy;
        data[base + 2] = c[0];
        data[base + 3] = c[1];
        data[base + 4] = c[2];
        data[base + 5] = a.selected ? 9.0 : 6.0;
        data[base + 6] = a.selected ? 1.0 : 0.0;
        data[base + 7] = 0;
      }
      this.device.queue.writeBuffer(this.instanceBuf, 0, data.subarray(0, n * 8));
      const enc = this.device.createCommandEncoder();
      const view = this.ctx.getCurrentTexture().createView();
      const pass = enc.beginRenderPass({
        colorAttachments: [{
          view,
          clearValue: { r: 0, g: 0, b: 0, a: 0 },
          loadOp: 'clear',
          storeOp: 'store',
        }],
      });
      pass.setPipeline(this.pipeline);
      pass.setBindGroup(0, this.bindGroup);
      pass.setVertexBuffer(0, this.instanceBuf);
      pass.draw(6, n);
      pass.end();
      this.device.queue.submit([enc.finish()]);
      return true;
    }

    clear() {
      if (!this.ready) return;
      const enc = this.device.createCommandEncoder();
      const view = this.ctx.getCurrentTexture().createView();
      const pass = enc.beginRenderPass({
        colorAttachments: [{
          view,
          clearValue: { r: 0, g: 0, b: 0, a: 0 },
          loadOp: 'clear',
          storeOp: 'store',
        }],
      });
      pass.end();
      this.device.queue.submit([enc.finish()]);
    }
  }

  global.EarthConsoleWebGPU = EarthConsoleWebGPU;
})(typeof window !== 'undefined' ? window : globalThis);
