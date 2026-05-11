# Praxis External-Service Cache Manifest

Status: experimental/review support artifact. This is not protected final
evidence by itself.

## Purpose

Some ToolSandbox scenarios call RapidAPI-backed external tools such as
`search_location_around_lat_lon`. RapidAPI has query limits. For repair and
review gates, SAGE may use a pre-existing external-service response cache so a
fresh SAGE arm can execute the same visible ToolSandbox call without spending
live RapidAPI quota.

This cache is distinct from SAGE task caching. It stores external API responses
keyed by request URL, host, and parameters. It does not store SAGE trajectories,
task labels, expected answers, or benchmark scores.

## Installed Local Cache

- Local path: `.secrets/rapid_api_cache.json`
- Git status: ignored by `.gitignore`; no API key is stored in the file.
- Source path copied locally:
  `../toolsandbox-sage-gap-closure-lab/.secrets/rapid_api_cache.json`
- Source/installed SHA-256:
  `3ed7732443c44d7d26e0f46ac32fa2e09fc773278368c6f13131021afafdbf25`
- Entry count: `71`
- Required run mode for quota preservation:
  `TOOLSANDBOX_RAPID_CACHE_MODE=read_only`
- Required cache path:
  `TOOLSANDBOX_RAPID_CACHE_PATH=.secrets/rapid_api_cache.json`

## Example Verified Cache Hit

The repaired bridge-policy gate verified this exact request without
`RAPID_API_KEY`:

```text
host: maps-data.p.rapidapi.com
url: https://maps-data.p.rapidapi.com/searchmaps.php
params:
  query: Whole Foods on Stevens Creek
  lat: 37.334606
  lng: -122.009102
  limit: 4
  country: us
  lang: en
cache key:
  65365e66e923642440a7596e912f95cb3bbb3797f62da8b4c462c21ccdcec571
first returned location:
  Whole Foods Market, 20955 Stevens Creek Blvd, Cupertino, CA 95014
  latitude 37.3235879, longitude -122.0396177
```

## Integrity Rule

Use the cache only as an external-service fixture. Do not use it to select
scenarios, infer labels, inspect expected answers, or reuse prior SAGE
trajectories. In `read_only` mode, cache misses fail visibly; they should not
fall through to live RapidAPI calls during quota-preserving diagnostics.

For protected final-claim validation, report the cache file hash and hit/miss
policy. If live external services are required instead, provision the same
service configuration for all matched arms and record that configuration.
