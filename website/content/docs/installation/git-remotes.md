---
title: "Git Remotes"
linkTitle: "Git Remotes"
weight: 50
description: "Authenticate with GitHub, GitLab, or Bitbucket"
depth: [advanced]
---

## Authentication with Your Git Remote

Authenticating with your git remote enables full aitasks functionality including task locking (prevents two agents from picking the same task), push/pull sync across machines, and issue integration (`ait issue-import`, `ait issue-update`).

### GitHub

Authenticate the GitHub CLI:

```bash
gh auth login
```

Follow the prompts to authenticate via browser or token.

### GitLab

Authenticate the GitLab CLI:

```bash
glab auth login
```

Follow the prompts to authenticate via browser or token. This also configures
git credentials for pushing to GitLab remotes.

### Bitbucket

Authenticate the Bitbucket CLI:

```bash
bkt auth login https://bitbucket.org --kind cloud --web
```

Follow the browser prompts to authenticate with your Atlassian account. For token-based
authentication (e.g., in CI environments):

```bash
bkt auth login https://bitbucket.org --kind cloud --username <email> --token <app-password>
```

Create an app password at: Settings > Personal Bitbucket settings > App passwords.
Enable the "Issues: read" and "Issues: write" permissions.

Note: `bkt` requires a context to be configured. After authentication, create one:

```bash
bkt context create myproject --host "https://api.bitbucket.org/2.0" \
    --workspace <your-workspace> --repo <your-repo> --set-active
```

---

**Next:** [Getting Started]({{< relref "/docs/getting-started" >}})
