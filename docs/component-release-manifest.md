<!-- Generated from config/release-components.yaml by eight_ball.manager.release. Do not edit by hand. -->

# Component release manifest

Customer installers consume `install/releases/v0.8.0/component-release-manifest.json`.
Catalog version `2026.08.01` is independent of installer suite `0.8.0`.
A catalog refresh does not install models.
The default chain remains `trial-install.sh`, `8.1.sh`, `8.2.sh`, `8.3.sh`.
Experimental scripts keep a letter suffix until they are assigned a permanent stage.
Hardware execution for every lane below is untested in this change.
Windows hardware execution is untested, and `pwsh` smoke steps are not run here.

Integrity is sha256 of each artifact plus a composite sha256.
Signed components use ed25519 over that composite digest.
Published components are unsigned until a release key is chosen.
A sha256 mismatch or a bad signature is rejected.
This manifest does not replace the existing v0.8.0 runtime-bundle pin.

| Consumer | OS | Lane | Entry point | Component | Hardware |
| --- | --- | --- | --- | --- | --- |
| funtech64/ycgpt-lightsail-installer#179 | linux | ubuntu/cpu | `install/ubuntu/trial-install.sh` | `ubuntu-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#179 | linux | ubuntu/cuda | `install/ubuntu/trial-install.sh` | `ubuntu-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#178 | darwin | mac/apple-silicon | `install/mac/apple-silicon/trial-install.sh` | `mac-apple-silicon-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#178 | darwin | mac/intel | `install/mac/intel/trial-install.sh` | `mac-intel-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#180 | windows | windows/cpu | `install/windows/cpu/trial-install.ps1` | `windows-cpu-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#180 | windows | windows/cuda | `install/windows/cuda/trial-install.ps1` | `windows-cuda-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#177 | linux | cloud/aws-lightsail/cpu | `install/cloud/aws-lightsail/cpu/trial-install.sh` | `lightsail-cpu-trial-chain` | untested |
| funtech64/ycgpt-lightsail-installer#177 | linux | cloud/aws-lightsail/gpu | `install/cloud/aws-lightsail/gpu/trial-install.sh` | `lightsail-gpu-trial-chain` | untested |
| public-install-tree | linux | cloud/digitalocean/cpu-droplet | `install/cloud/digitalocean/cpu-droplet/trial-install.sh` | `digitalocean-cpu-trial-chain` | untested |
| public-install-tree | linux | cloud/digitalocean/gpu-droplet | `install/cloud/digitalocean/gpu-droplet/trial-install.sh` | `digitalocean-gpu-trial-chain` | untested |

## Experimental manager

`install/shared/8.4a-model-manager.sh` is optional, letter-suffixed, and outside the default chain.
