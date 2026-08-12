# DigitalOcean base-pilot CPU selection

Snapshot: `2026-08-12`

## Selection algorithm

For each allowed CPU family, sort plans by (memory_gib, vcpus, boot_disk_gib, provider_size_slug) ascending, then select 6 evenly distributed indices with `index_i = round(i * (n - 1) / ({SELECTION_COUNT} - 1))` for i in 0..{SELECTION_COUNT - 1}, always including the smallest and largest available entry.

## Selected CPU slugs by family

### `basic`

- `s-1vcpu-1gb`
- `s-1vcpu-2gb`
- `s-2vcpu-2gb`
- `s-4vcpu-8gb`
- `s-8vcpu-16gb`
- `s-8vcpu-32gb`

### `cpu-optimized`

- `c-2vcpu-4gb`
- `c-4vcpu-8gb`
- `c-8vcpu-16gb`
- `c-16vcpu-32gb`
- `c-32vcpu-64gb`
- `c-48vcpu-96gb`

### `general-purpose`

- `g-2vcpu-8gb`
- `g-4vcpu-16gb`
- `g-8vcpu-32gb`
- `g-16vcpu-64gb`
- `g-32vcpu-128gb`
- `g-40vcpu-160gb`

### `memory-optimized`

- `m-2vcpu-16gb`
- `m-4vcpu-32gb`
- `m-8vcpu-64gb`
- `m-16vcpu-128gb`
- `m-24vcpu-192gb`
- `m-32vcpu-256gb`

## GPU on-demand slugs (all nine documented self-service plans)

- `gpu-4000adax1-20gb`
- `gpu-6000adax1-48gb`
- `gpu-h100x1-80gb`
- `gpu-h100x8-640gb`
- `gpu-h200x1-141gb`
- `gpu-h200x8-1128gb`
- `gpu-l40sx1-48gb`
- `gpu-mi300x1-192gb`
- `gpu-mi300x8-1536gb`
