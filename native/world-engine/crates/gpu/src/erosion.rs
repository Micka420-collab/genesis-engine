//! Hydraulic erosion on GPU via wgpu compute.
//!
//! Algorithm: parallel droplet simulation. Each droplet is independent
//! at the macro level (different starting positions); within a droplet's
//! lifetime the loop is serial, but we run many droplets in parallel.
//!
//! Determinism: starting positions are derived from `(seed, droplet_id)`
//! exactly the same way as the CPU implementation, so the cross-backend
//! equivalence test in `tests/cross_backend.rs` (TODO) can hold.

use crate::GpuError;
use bytemuck::{Pod, Zeroable};
use genesis_terrain::Heightmap;

/// Uniforms passed to the shader.
#[repr(C)]
#[derive(Copy, Clone, Pod, Zeroable, bytemuck_derive::Pod, bytemuck_derive::Zeroable)]
struct ErosionUniforms {
    width: u32,
    height: u32,
    n_droplets: u32,
    max_steps: u32,
    seed_lo: u32,
    seed_hi: u32,
    inertia: f32,
    erode_speed: f32,
    deposit_speed: f32,
    evaporate_speed: f32,
    gravity: f32,
    capacity_factor: f32,
    min_capacity: f32,
    _pad0: f32,
    _pad1: f32,
    _pad2: f32,
}

/// GPU hydraulic eroder.
pub struct HydraulicErosionGpu {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::ComputePipeline,
    bind_group_layout: wgpu::BindGroupLayout,
}

impl HydraulicErosionGpu {
    /// Create a new GPU eroder. Picks the default adapter.
    pub fn try_new() -> Result<Self, GpuError> {
        pollster::block_on(Self::try_new_async())
    }

    async fn try_new_async() -> Result<Self, GpuError> {
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::default());
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                ..Default::default()
            })
            .await
            .ok_or(GpuError::NoAdapter)?;

        let (device, queue) = adapter
            .request_device(
                &wgpu::DeviceDescriptor {
                    label: Some("genesis-gpu device"),
                    required_features: wgpu::Features::empty(),
                    required_limits: wgpu::Limits::downlevel_defaults(),
                    memory_hints: wgpu::MemoryHints::Performance,
                },
                None,
            )
            .await
            .map_err(|e| GpuError::Device(e.to_string()))?;

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("erosion.wgsl"),
            source: wgpu::ShaderSource::Wgsl(EROSION_WGSL.into()),
        });

        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("erosion bgl"),
            entries: &[
                // uniforms
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::COMPUTE,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Uniform,
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
                // heightmap (rw)
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::COMPUTE,
                    ty: wgpu::BindingType::Buffer {
                        ty: wgpu::BufferBindingType::Storage { read_only: false },
                        has_dynamic_offset: false,
                        min_binding_size: None,
                    },
                    count: None,
                },
            ],
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("erosion pipeline layout"),
            bind_group_layouts: &[&bind_group_layout],
            push_constant_ranges: &[],
        });

        let pipeline = device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: Some("erosion pipeline"),
            layout: Some(&pipeline_layout),
            module: &shader,
            entry_point: "main",
            compilation_options: wgpu::PipelineCompilationOptions::default(),
            cache: None,
        });

        Ok(Self {
            device,
            queue,
            pipeline,
            bind_group_layout,
        })
    }

    /// Erode the heightmap in place. `n_droplets` should be a multiple of 64
    /// (the workgroup size). Returns the heightmap untouched on success.
    pub fn erode(
        &self,
        hm: &mut Heightmap,
        seed: u64,
        n_droplets: u32,
        max_steps: u32,
    ) -> Result<(), GpuError> {
        let n_pixels = (hm.width * hm.height) as u64;
        let buffer_size = n_pixels * std::mem::size_of::<f32>() as u64;

        let uniforms = ErosionUniforms {
            width: hm.width,
            height: hm.height,
            n_droplets,
            max_steps,
            seed_lo: seed as u32,
            seed_hi: (seed >> 32) as u32,
            inertia: 0.05,
            erode_speed: 0.3,
            deposit_speed: 0.3,
            evaporate_speed: 0.01,
            gravity: 4.0,
            capacity_factor: 4.0,
            min_capacity: 0.01,
            _pad0: 0.0,
            _pad1: 0.0,
            _pad2: 0.0,
        };

        let uni_buf = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("erosion uniforms"),
            size: std::mem::size_of::<ErosionUniforms>() as u64,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        self.queue
            .write_buffer(&uni_buf, 0, bytemuck::bytes_of(&uniforms));

        let hm_buf = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("heightmap storage"),
            size: buffer_size,
            usage: wgpu::BufferUsages::STORAGE
                | wgpu::BufferUsages::COPY_SRC
                | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        self.queue
            .write_buffer(&hm_buf, 0, bytemuck::cast_slice(&hm.data));

        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("erosion bind group"),
            layout: &self.bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: uni_buf.as_entire_binding(),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: hm_buf.as_entire_binding(),
                },
            ],
        });

        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("erosion encoder"),
            });
        {
            let mut cpass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor {
                label: Some("erosion cpass"),
                timestamp_writes: None,
            });
            cpass.set_pipeline(&self.pipeline);
            cpass.set_bind_group(0, &bind_group, &[]);
            let workgroups = (n_droplets + 63) / 64;
            cpass.dispatch_workgroups(workgroups, 1, 1);
        }

        let readback = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("readback"),
            size: buffer_size,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        encoder.copy_buffer_to_buffer(&hm_buf, 0, &readback, 0, buffer_size);
        self.queue.submit(Some(encoder.finish()));

        let slice = readback.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |r| {
            let _ = tx.send(r);
        });
        self.device.poll(wgpu::Maintain::Wait);
        let _ = rx.recv().map_err(|e| GpuError::Device(e.to_string()))?;
        let mapped = slice.get_mapped_range();
        let floats: &[f32] = bytemuck::cast_slice(&mapped);
        hm.data.copy_from_slice(floats);
        drop(mapped);
        readback.unmap();
        Ok(())
    }
}

const EROSION_WGSL: &str = include_str!("erosion.wgsl");
