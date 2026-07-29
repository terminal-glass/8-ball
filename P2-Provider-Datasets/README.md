# P2 Provider Datasets

This directory is the static provider-specification catalog for NoCloudGPT deployment planning. It contains metadata only; it does not include recommendation logic, installer logic, generated installers, model payloads, or `8.sh` generation.

## Provider datasets

* `providers/digitalocean/` contains DigitalOcean Droplet plan metadata grouped by Basic, General Purpose, CPU Optimized, Memory Optimized, and Storage Optimized families.
* `providers/lightsail/` contains AWS Lightsail Linux/Unix public IPv4 bundle metadata and excludes Windows bundles.
* `providers/common/` contains shared terminology for architectures, units, billing terms, bandwidth, and provider identifiers.

## NoCloudGPT datasets

`providers/nocloudgpt/` contains internal planning templates and appliance overhead metadata. These documents are explicitly separate from cloud-provider specifications.

## Validation process

Run the offline test suite from the repository root:

```bash
python3 P2-Provider-Datasets/tests/test_p2_datasets.py
```

The tests parse every JSON document, validate schema coverage, enforce unique identifiers, validate numeric fields, verify provider identifiers, and check index consistency.

## Update process

1. Review official provider documentation.
2. Update only the relevant provider JSON documents.
3. Use `null` where a value cannot be verified from an official source.
4. Regenerate indexes and reports.
5. Run the offline tests.

## Relationship to P1 and P3

P1 consumes provider data. P3 provides Ollama model metadata. Future compatibility logic will combine both datasets, but this P2 library intentionally does not implement compatibility or recommendation logic.
