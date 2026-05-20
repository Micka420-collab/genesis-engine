// Hydraulic erosion — parallel droplet simulation.
//
// One invocation = one droplet. Droplets share the same heightmap via
// atomic-friendly racy writes; bilinear deposits/erodes are NOT exact
// (deliberately — the CPU version uses sequential writes that don't
// race). Cross-backend equivalence is tested with a tolerance, not bit
// equality.

struct Uniforms {
    width:            u32,
    height:           u32,
    n_droplets:       u32,
    max_steps:        u32,
    seed_lo:          u32,
    seed_hi:          u32,
    inertia:          f32,
    erode_speed:      f32,
    deposit_speed:    f32,
    evaporate_speed:  f32,
    gravity:          f32,
    capacity_factor:  f32,
    min_capacity:     f32,
    _pad0:            f32,
    _pad1:            f32,
    _pad2:            f32,
};

@group(0) @binding(0) var<uniform> U : Uniforms;
@group(0) @binding(1) var<storage, read_write> heightmap : array<f32>;

fn idx(i: u32, j: u32) -> u32 {
    return j * U.width + i;
}

// Cheap deterministic hash (splitmix64-style folded to f32).
fn hash_u32(x: u32) -> u32 {
    var v: u32 = x;
    v = v ^ (v >> 16u);
    v = v * 0x7feb352du;
    v = v ^ (v >> 15u);
    v = v * 0x846ca68bu;
    v = v ^ (v >> 16u);
    return v;
}

fn rand01(x: u32) -> f32 {
    return f32(hash_u32(x) & 0x00FFFFFFu) / 16777216.0;
}

fn sample_h(i: i32, j: i32) -> f32 {
    let w = i32(U.width);
    let h = i32(U.height);
    let ii = clamp(i, 0, w - 1);
    let jj = clamp(j, 0, h - 1);
    return heightmap[idx(u32(ii), u32(jj))];
}

fn bilinear_add(i: i32, j: i32, ox: f32, oy: f32, amount: f32) {
    let w00 = (1.0 - ox) * (1.0 - oy);
    let w10 = ox * (1.0 - oy);
    let w01 = (1.0 - ox) * oy;
    let w11 = ox * oy;
    let w = i32(U.width);
    let h = i32(U.height);
    if (i >= 0 && j >= 0 && i + 1 < w && j + 1 < h) {
        heightmap[idx(u32(i),     u32(j))]     = heightmap[idx(u32(i),     u32(j))]     + amount * w00;
        heightmap[idx(u32(i + 1), u32(j))]     = heightmap[idx(u32(i + 1), u32(j))]     + amount * w10;
        heightmap[idx(u32(i),     u32(j + 1))] = heightmap[idx(u32(i),     u32(j + 1))] + amount * w01;
        heightmap[idx(u32(i + 1), u32(j + 1))] = heightmap[idx(u32(i + 1), u32(j + 1))] + amount * w11;
    }
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid : vec3<u32>) {
    let did = gid.x;
    if (did >= U.n_droplets) { return; }

    let seed_a = U.seed_lo ^ (did * 0x9E3779B9u);
    let seed_b = U.seed_hi ^ (did * 0x85EBCA6Bu);
    var px = rand01(seed_a) * f32(U.width  - 2u);
    var py = rand01(seed_b) * f32(U.height - 2u);

    var dir_x: f32 = 0.0;
    var dir_y: f32 = 0.0;
    var speed: f32 = 1.0;
    var water: f32 = 1.0;
    var sediment: f32 = 0.0;

    for (var step: u32 = 0u; step < U.max_steps; step = step + 1u) {
        let nx = i32(floor(px));
        let ny = i32(floor(py));
        if (nx < 1 || ny < 1 || nx >= i32(U.width)  - 2 || ny >= i32(U.height) - 2) {
            break;
        }
        let ox = px - f32(nx);
        let oy = py - f32(ny);

        let h_nw = sample_h(nx,     ny);
        let h_ne = sample_h(nx + 1, ny);
        let h_sw = sample_h(nx,     ny + 1);
        let h_se = sample_h(nx + 1, ny + 1);

        let g_x = (h_ne - h_nw) * (1.0 - oy) + (h_se - h_sw) * oy;
        let g_y = (h_sw - h_nw) * (1.0 - ox) + (h_se - h_ne) * ox;
        let current_h =
              h_nw * (1.0 - ox) * (1.0 - oy)
            + h_ne * ox * (1.0 - oy)
            + h_sw * (1.0 - ox) * oy
            + h_se * ox * oy;

        dir_x = dir_x * U.inertia - g_x * (1.0 - U.inertia);
        dir_y = dir_y * U.inertia - g_y * (1.0 - U.inertia);
        let len = sqrt(dir_x * dir_x + dir_y * dir_y);
        if (len < 1e-6) { break; }
        dir_x = dir_x / len;
        dir_y = dir_y / len;

        let nx2 = px + dir_x;
        let ny2 = py + dir_y;
        if (nx2 < 1.0 || ny2 < 1.0 || nx2 >= f32(U.width) - 2.0 || ny2 >= f32(U.height) - 2.0) {
            break;
        }

        let nnx = i32(floor(nx2));
        let nny = i32(floor(ny2));
        let nox = nx2 - f32(nnx);
        let noy = ny2 - f32(nny);
        let new_h_nw = sample_h(nnx,     nny);
        let new_h_ne = sample_h(nnx + 1, nny);
        let new_h_sw = sample_h(nnx,     nny + 1);
        let new_h_se = sample_h(nnx + 1, nny + 1);
        let new_h =
              new_h_nw * (1.0 - nox) * (1.0 - noy)
            + new_h_ne * nox * (1.0 - noy)
            + new_h_sw * (1.0 - nox) * noy
            + new_h_se * nox * noy;
        let delta_h = new_h - current_h;

        var capacity = -delta_h * speed * water * U.capacity_factor;
        if (capacity < U.min_capacity) { capacity = U.min_capacity; }

        if (sediment > capacity || delta_h > 0.0) {
            var deposit: f32;
            if (delta_h > 0.0) {
                deposit = min(delta_h, sediment);
            } else {
                deposit = (sediment - capacity) * U.deposit_speed;
            }
            sediment = sediment - deposit;
            bilinear_add(nx, ny, ox, oy, deposit);
        } else {
            let erode = min((capacity - sediment) * U.erode_speed, -delta_h);
            sediment = sediment + erode;
            bilinear_add(nx, ny, ox, oy, -erode);
        }

        let v2 = speed * speed + delta_h * U.gravity;
        if (v2 > 0.0) { speed = sqrt(v2); } else { speed = 0.0; }
        water = water * (1.0 - U.evaporate_speed);
        px = nx2;
        py = ny2;
    }
}
