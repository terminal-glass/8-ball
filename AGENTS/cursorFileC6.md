CursorFileC6 — CSV Import and Deduplication Checklist

Purpose

Safely import the provider, laptop, accelerator, CUDA, ROCm, and measured-host CSV files stored under AGENTS/ without combining unrelated tables, double-counting records, or allowing lower-confidence assumptions to overwrite stronger evidence.

This is a C5 data-ingestion gate.

It does not replace the C5 generated page tree.
It does not wire 8.2 to the manifest.
It does not claim measured model compatibility.

Source Files

Classify the existing AGENTS/TG-8Ball-*.csv files into these namespaces before importing any rows.

1. Provider instance data

Examples:

• AWS Lightsail CPU bundles
• DigitalOcean CPU droplets
• AWS Lightsail for Research GPU plans
• DigitalOcean NVIDIA GPU Droplets
• DigitalOcean AMD GPU Droplets

Destination concept:

provider_instance_data

2. Assumed hardware profiles

Examples:

• Mac laptop assumptions
• Windows laptop assumptions
• generic CUDA server assumptions

Destination concept:

assumed_hardware_profiles

3. Measured hardware inventory

Examples:

• brain1 RTX 3060 host
• future hosts captured from nvidia-smi, ROCm, system RAM, CPU, and disk measurements

Destination concept:

measured_hardware_inventory

4. Classification data

Examples:

• accelerator classes
• deployment type IDs 3, 4, 5, 6, and 7
• CPU-only, CUDA, ROCm, Apple Metal, Vulkan, and unknown-GPU classifications

Destination concept:

classification_data

5. Control and provenance files

Examples:

• source inventories
• recovered counts
• Cursor checklists
• XLSX summaries

Destination concept:

control_and_provenance

These files must never be imported as hardware records.

Stable Deduplication Keys

Use table-specific keys.

Provider instance record

Composite key:

```text
provider + product_line + provider_plan_id
```

If the source does not expose a provider plan ID, use the explicitly assigned internal plan ID. Do not use display name alone.

Assumed hardware profile

Key:

```text
profile_id
```

Measured host

Key:

```text
host_profile_id
```

Accelerator class

Key:

```text
accelerator_class_id
```

Deployment type

Key:

```text
deployment_type_id
```

Valid stable deployment type IDs remain:

```text
3, 4, 5, 6, 7
```

Fields That Are Not Unique Keys

Never deduplicate records solely because these values match:

• deployment type ID
• provider name
• display name
• menu label
• GPU model
• RAM amount
• VRAM amount
• CPU count
• storage amount
• accelerator type
• model recommendation

Multiple valid records may share all or several of these values.

Evidence Precedence

When two rows genuinely target the same stable key, preserve the strongest evidence level.

Precedence order:

```text
measured_host_inventory
> provider_published
> validated_internal_planning
> assumed_client_class / assumed_server_class
> unknown
```

Rules:

• Never allow an assumption row to overwrite a measured host row.
• Never allow an assumption row to overwrite a provider-published plan.
• Preserve conflicting values in an audit report instead of silently choosing one.
• Preserve source path, source date, and provenance status with every imported row.
• A provider-published hardware specification is not a measured Ollama compatibility result.
• A successful hardware detection is not automatically a successful model benchmark.

Expected Intentional Overlap

The following are relationships, not duplicates:

• many hardware records mapping to deployment type 3–7;
• Windows NVIDIA laptops and Linux CUDA servers sharing VRAM bands;
• DigitalOcean CPU and GPU products sharing the same provider;
• ordinary AWS Lightsail and Lightsail for Research sharing the AWS brand;
• accelerator classes appearing in multiple hardware profiles;
• source inventory files mentioning records that also exist in data files;
• provider counts summarizing records already represented elsewhere;
• generic CUDA tiers overlapping measured host capabilities.

Do not remove rows merely because these overlaps exist.

Import Requirements

☐ Discover all AGENTS/TG-8Ball-*.csv files.
☐ Classify every file into exactly one namespace.
☐ Reject unknown file types until manually classified.
☐ Parse CSV using header names, not column position assumptions.
☐ Validate required fields for each namespace.
☐ Normalize booleans, integer values, decimal values, and null/unknown values consistently.
☐ Preserve original source filenames.
☐ Preserve provenance status.
☐ Preserve source notes and warnings.
☐ Generate stable internal IDs only when a source ID is unavailable.
☐ Do not import control/provenance rows as hardware.
☐ Do not concatenate all CSV files into one generic table.
☐ Do not mark any model as measured-compatible from these CSVs alone.

Validation Failures

Validation must fail when:

☐ duplicate profile_id exists within assumed hardware profiles;
☐ duplicate host_profile_id exists within measured host inventory;
☐ duplicate accelerator_class_id exists;
☐ duplicate provider composite keys exist;
☐ a deployment type outside 3–7 is introduced without a separate approved contract change;
☐ a checklist, count file, source inventory, or XLSX summary is treated as hardware data;
☐ a lower-confidence record overwrites stronger evidence;
☐ required provenance is missing;
☐ a provider-published row is labeled as measured model compatibility;
☐ a measured GPU detection is labeled as a successful Ollama model benchmark without test evidence;
☐ conflicting values are silently discarded;
☐ generated records reference 02-models.

Required Audit Outputs

Create a machine-readable import report and a human-readable summary.

Suggested outputs:

```text
data/generated/provider-import-report.json
docs/C5.1-csv-import-report.md
```

The report must include:

• files discovered;
• file namespace assigned;
• rows read;
• rows imported;
• intentional overlaps;
• true duplicate keys;
• conflicting values;
• rejected rows;
• unknown/unproven fields;
• provenance counts;
• provider counts;
• assumed profile counts;
• measured host counts;
• accelerator class counts.

C5 Integration

Only after this checklist passes:

• update the canonical provider/hardware configuration;
• regenerate data/generated/pages/;
• enrich install-manifest.json with provider and accelerator compatibility;
• validate page and manifest counts;
• keep existing model/deployment identity stable;
• preserve deployment type IDs 3–7;
• keep models/, never 02-models.

Do not wire 8.2 to enriched provider selection until this import gate and generated-page validation both pass.

Tests

Add tests proving:

☐ every CSV is classified;
☐ control/provenance CSVs are excluded from hardware imports;
☐ stable keys are unique within their namespaces;
☐ intentional overlap is retained;
☐ evidence precedence is enforced;
☐ conflicts are reported;
☐ unknown values remain unknown;
☐ no measured compatibility is invented;
☐ deployment types remain 3–7;
☐ no code or generated page references 02-models.

Run:

```text
python3 -m pytest -q
python3 -m eight_ball validate-pages
bash scripts/validate-catalog.sh
```

Run the catalog validation script only if it exists.

Completion Report

Cursor must report:

• files changed;
• all CSV files discovered;
• namespace assigned to each file;
• stable keys used;
• rows imported by namespace;
• true duplicate keys found;
• intentional overlaps retained;
• conflicts requiring human review;
• provenance-level counts;
• generated files changed;
• tests run and exact results;
• confirmation that 8.2 was not wired or modified as part of this checklist unless separately instructed.

Stop Conditions

Stop and report instead of guessing when:

• a CSV cannot be classified;
• a provider plan lacks both a provider ID and an approved internal ID;
• two source rows claim the same stable key with conflicting provider-published or measured values;
• provenance is missing;
• a required schema decision is not documented;
• importing the files would require changing deployment type identity.