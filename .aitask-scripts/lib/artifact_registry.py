#!/usr/bin/env python3
"""artifact_registry.py - backend registry for the unified artifact model
(t1076_3; design: aidocs/unified_artifact_design.md par.6).

Resolves backend NAMES (the value stored in each artifact manifest's `backend`
field) against the git-tracked project config's `artifacts:` block:

    artifacts:
      default_backend: dir          # optional; `local` when absent
      backends:
        dir:
          path: /mnt/share/ait-artifacts   # required, absolute

The registry owns REGISTRATION + CONFIGURATION validation (is the name in
config, are required keys present and sane); the bash dispatcher
(lib/artifact_backend.sh) remains the ADAPTER authority (which artifact_<n>_*
function families exist). `local` is always implicitly registered and needs no
config. Backend names are adapter names (t1076_3 settled decision: one
instance per adapter; multi-instance indirection deliberately rejected until
a second instance is actually wanted).

Secrets NEVER live in this config block: it carries only non-secret
coordinates (paths, endpoints, bucket names). Credentials for remote backends
(s3: t1089, gdrive: t1090) go in env vars or gitignored per-user files.

CONFIG LOADING IS FAIL-CLOSED and deliberately does NOT reuse
config_utils.load_yaml_config: that helper returns {} for a syntactically
valid file whose root is not a mapping, which would silently treat a broken
(list-shaped) project_config.yaml as "no config" and fail open to `local`.
Here: missing file / empty file -> no config (zero-config default `local`);
YAML parse error or non-mapping root -> die naming the file and the problem.
"""

import os
import re
import sys

import yaml

BACKEND_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")  # artifact_manifest.py shape

# BACKEND-EXTENSION-POINT (registry): adapter name -> {config_key: (ENV_VAR, validator)}.
# Validators: "abs_path" (non-empty absolute path), "nonempty" (non-empty string).
KNOWN_ADAPTERS = {
    "dir": {"path": ("ARTIFACT_DIR_ROOT", "abs_path")},
    # s3 (t1089) and gdrive (t1090) add their entries here.
}


def die(msg):
    sys.stderr.write("artifact_registry.py: " + msg + "\n")
    sys.exit(1)


def load_config(path):
    """Load the project config, fail-closed on a malformed file.

    Returns {} when the file is missing or empty; dies on a YAML parse error
    or a present-but-non-mapping root (never silently fail open to `local`).
    """
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        die("%s: YAML parse error: %s" % (path, exc))
    if data is None:
        return {}
    if not isinstance(data, dict):
        die("%s: top-level YAML is not a mapping — fix the file" % path)
    return data


def registered_backends(config, path):
    """Return the validated `artifacts.backends` mapping ({} when absent)."""
    artifacts = config.get("artifacts")
    if artifacts is None:
        return {}
    if not isinstance(artifacts, dict):
        die("%s: `artifacts:` is not a mapping — fix the file" % path)
    backends = artifacts.get("backends")
    if backends is None:
        return {}
    if not isinstance(backends, dict):
        die("%s: `artifacts.backends:` is not a mapping — fix the file" % path)
    for name, entry in backends.items():
        if not isinstance(name, str) or not BACKEND_RE.match(name):
            die("%s: invalid backend name %r under artifacts.backends "
                "(want [a-z0-9][a-z0-9_-]{0,31})" % (path, name))
        if not isinstance(entry, dict):
            die("%s: artifacts.backends.%s is not a mapping — fix the file"
                % (path, name))
    return backends


def validate_value(name, key, value, validator, path):
    if not isinstance(value, str) or not value.strip():
        die("%s: backend '%s': required key '%s' missing or empty"
            % (path, name, key))
    value = value.strip()
    if validator == "abs_path" and not os.path.isabs(value):
        die("%s: backend '%s': '%s' must be an absolute path (got %r) — a "
            "relative path is cwd-ambiguous across checkouts"
            % (path, name, key, value))
    return value


def cmd_backend_env(config, path, name):
    """Print one ENV_VAR=value line per adapter param; nothing for `local`."""
    if name == "local":
        return
    backends = registered_backends(config, path)
    if name not in backends:
        die("backend '%s' is not registered — add artifacts.backends.%s to %s"
            % (name, name, path))
    if name not in KNOWN_ADAPTERS:
        die("no adapter for backend '%s' (known: %s; s3/gdrive arrive with "
            "t1089/t1090)" % (name, ", ".join(["local"] + sorted(KNOWN_ADAPTERS))))
    entry = backends[name]
    for key, (env_var, validator) in sorted(KNOWN_ADAPTERS[name].items()):
        value = validate_value(name, key, entry.get(key), validator, path)
        print("%s=%s" % (env_var, value))


def cmd_default_backend(config, path):
    """Print the create-time default backend (`local` when unconfigured)."""
    artifacts = config.get("artifacts")
    if artifacts is not None and not isinstance(artifacts, dict):
        die("%s: `artifacts:` is not a mapping — fix the file" % path)
    default = (artifacts or {}).get("default_backend")
    if default is None:
        print("local")
        return
    if not isinstance(default, str) or not BACKEND_RE.match(default):
        die("%s: artifacts.default_backend is not a valid backend name: %r"
            % (path, default))
    if default != "local":
        backends = registered_backends(config, path)
        if default not in backends:
            die("%s: artifacts.default_backend '%s' is not registered under "
                "artifacts.backends" % (path, default))
        if default not in KNOWN_ADAPTERS:
            die("%s: artifacts.default_backend '%s' has no adapter (known: %s)"
                % (path, default, ", ".join(["local"] + sorted(KNOWN_ADAPTERS))))
    print(default)


def cmd_list(config, path):
    """Print registered backend names, `local` (always registered) first."""
    print("local")
    for name in sorted(registered_backends(config, path)):
        if name != "local":
            print(name)


def main(argv):
    if len(argv) < 3 or argv[0] != "--config":
        die("usage: artifact_registry.py --config <path> "
            "<backend-env|default-backend|list> ...")
    path = argv[1]
    cmd = argv[2]
    rest = argv[3:]
    config = load_config(path)
    if cmd == "backend-env":
        if len(rest) != 1:
            die("backend-env <name>")
        cmd_backend_env(config, path, rest[0])
    elif cmd == "default-backend":
        if rest:
            die("default-backend takes no arguments")
        cmd_default_backend(config, path)
    elif cmd == "list":
        if rest:
            die("list takes no arguments")
        cmd_list(config, path)
    else:
        die("unknown subcommand: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
