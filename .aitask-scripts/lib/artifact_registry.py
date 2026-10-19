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
        gitbranch:
          branch: aitask-artifacts         # required, a git branch name

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
# Validators: "abs_path" (non-empty absolute path), "nonempty" (non-empty
# string), "ref_name" (a git branch name, never a reserved framework branch).
KNOWN_ADAPTERS = {
    "dir": {"path": ("ARTIFACT_DIR_ROOT", "abs_path")},
    "gitbranch": {"branch": ("ARTIFACT_GITBRANCH_BRANCH", "ref_name")},
    # s3 (t1089) and gdrive (t1090) add their entries here.
}

# Branches the gitbranch store may never be pointed at: the code branches and
# the framework's own orphan branches (the aitask_web_merge.sh skip set).
# Pointing the blob store at `main` must be impossible, not discouraged.
RESERVED_REFS = ("main", "master", "aitask-data", "aitask-locks", "aitask-ids")
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]*")


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


def check_ref_name(value):
    """Return why <value> is not an acceptable gitbranch branch, or None.

    The ONE definition of the rule: activation (validate_value) and the
    `validate-ref` verb (the settings TUI's pre-registration check) both call
    it, so they cannot disagree. A conservative subset of git's
    check-ref-format: shell-safe characters only, no empty / dot-led / .lock
    components, nothing git itself would refuse.
    """
    if not isinstance(value, str) or not value:
        return "must be a non-empty branch name"
    # fullmatch: `$` under re.match also accepts a trailing newline.
    if not REF_RE.fullmatch(value):
        return ("must start with a letter or digit and use only "
                "[A-Za-z0-9._/-] (got %r)" % value)
    if ".." in value or "//" in value or "@{" in value or value.endswith("/"):
        return "is not a valid git branch name (got %r)" % value
    for comp in value.split("/"):
        if comp.startswith(".") or comp.endswith(".") or comp.endswith(".lock"):
            return "is not a valid git branch name (got %r)" % value
    if value == "HEAD":
        return "must not be HEAD"
    if value in RESERVED_REFS:
        return ("must not be the reserved branch %r (reserved: %s) — the "
                "artifact store needs a branch of its own"
                % (value, ", ".join(RESERVED_REFS)))
    return None


def validate_value(name, key, value, validator, path):
    if not isinstance(value, str) or not value.strip():
        die("%s: backend '%s': required key '%s' missing or empty"
            % (path, name, key))
    if validator == "ref_name":
        # The RAW value, exactly as validate-ref sees it: stripping first would
        # let activation accept what the settings-time check rejects.
        why = check_ref_name(value)
        if why:
            die("%s: artifacts.backends.%s.%s %s" % (path, name, key, why))
        return value
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


def cmd_adapters():
    """Print every AVAILABLE adapter, `local` first, independent of config.

    `list` prints only what is registered, so on a fresh project an adapter
    could never be selected to create its own first configuration.
    """
    print("local")
    for name in sorted(KNOWN_ADAPTERS):
        print(name)


def cmd_validate_ref(value):
    """Exit 0 when <value> is an acceptable gitbranch branch, else 1 + why."""
    why = check_ref_name(value)
    if why:
        die("artifacts.backends.gitbranch.branch %s" % why)


def main(argv):
    if len(argv) < 3 or argv[0] != "--config":
        die("usage: artifact_registry.py --config <path> "
            "<backend-env|default-backend|list|adapters|validate-ref> ...")
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
    elif cmd == "adapters":
        if rest:
            die("adapters takes no arguments")
        cmd_adapters()
    elif cmd == "validate-ref":
        if len(rest) != 1:
            die("validate-ref <branch>")
        cmd_validate_ref(rest[0])
    else:
        die("unknown subcommand: " + cmd)


if __name__ == "__main__":
    main(sys.argv[1:])
