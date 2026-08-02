# 8\-BALL Profiles

This directory is the repo\-side scaffold for 8\-BALL environment profile artifacts\.

Runtime installers should use a writable profile directory, normally:

```bash
/opt/philosopher/profiles
```

The legacy file remains supported:

```bash
/opt/philosopher/instance.env
```

Future `8.2` work should load a designated profile directory first, then fall
back to the legacy `instance.env` behavior when no profile directory has been
declared\.

Decision\-sequence folders:

```text
01-families/
02-models/
03-deployment-types/
04-hard-disk/
05-ram/
06-cpu/
07-gpu/
generated/
```

Use `.md` files for human\-readable source artifacts\. Use generated `.json` and
`.env` files for anything `8.2`, `8.3`, the website selector, or Docker routing
will consume\.

Do not store secrets in profile artifacts\. Passport/license tokens, Stripe
keys, S3 URLs, or customer credentials belong in the authenticated installer
flow, not in these environment files\.
