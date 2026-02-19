# Website Local Development

This guide explains how to set up your local machine to work on the aitasks documentation website, which is built with [Hugo](https://gohugo.io/) and the [Docsy](https://www.docsy.dev/) theme.

The website source lives in the `website/` directory of the repository.

## Required Tools

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| [Hugo](https://gohugo.io/) extended edition | 0.155.3 | Static site generator |
| [Go](https://go.dev/) | 1.23 | Required for Hugo Modules |
| [Dart Sass](https://sass-lang.com/dart-sass/) | 1.97 | SCSS compilation (required by Docsy theme) |
| [Node.js](https://nodejs.org/) | 18+ | Required for PostCSS (used by Docsy theme) |

Hugo **extended edition** is required because the Docsy theme uses SCSS for styling. Node.js is required because Docsy uses PostCSS for CSS processing.

## Installation

### Arch Linux

```bash
sudo pacman -S hugo go dart-sass nodejs npm
```

The Arch `hugo` package includes the extended edition by default.

After installing system packages, install the Node.js dependencies:

```bash
cd website
npm install
```

### macOS (Homebrew)

```bash
brew install hugo go sass/sass/sass node
```

Then install Node.js dependencies:
```bash
cd website && npm install
```

### Ubuntu / Debian

```bash
# Hugo extended - use the official .deb from GitHub releases
# (the apt package may be outdated or missing the extended edition)
# See: https://gohugo.io/installation/linux/#debian

# Go
sudo apt install golang-go

# Dart Sass
sudo snap install dart-sass

# Node.js
sudo apt install nodejs npm
```

For Hugo on Ubuntu, it's recommended to download the latest extended `.deb` package from the [Hugo releases page](https://github.com/gohugoio/hugo/releases) to ensure you get the extended edition.

After installing system packages, install the Node.js dependencies:
```bash
cd website && npm install
```

### Windows (via WSL)

Follow the Ubuntu/Debian instructions inside your WSL distribution.

## Verify Installation

Run these commands to verify everything is installed correctly:

```bash
hugo version    # Should show "extended" in the output
go version      # Should show >= 1.23
sass --version  # Should show >= 1.97
node --version  # Should show >= 18
```

## Running the Site Locally

First, ensure Node.js dependencies are installed:
```bash
cd website
npm install
```

Then start the development server:
```bash
hugo server
```

The site will be available at `http://localhost:1313/aitasks/`.

Hugo watches for file changes and automatically rebuilds, so you can edit content and see changes in real time.

### First Run

On the first run, Hugo will download the Docsy theme module automatically. This may take a minute. Subsequent runs use the cached module.

If you see module errors, try:

```bash
cd website
hugo mod tidy
hugo mod get -u
```

## Common Issues

### SCSS compilation errors

If you see SCSS-related errors, verify that:
1. You have the **extended** edition of Hugo (`hugo version` should include "extended")
2. Dart Sass is installed and accessible (`sass --version`)
3. The placeholder files exist:
   - `website/assets/scss/_variables_project.scss`
   - `website/assets/scss/_styles_project.scss`

### PostCSS not found

If you see an error like `binary with name "postcss" not found`:
1. Ensure Node.js is installed: `node --version`
2. Run `cd website && npm install` to install PostCSS and autoprefixer
3. Verify `website/node_modules/.bin/postcss` exists

### Module download failures

If `hugo mod get` fails:
1. Check your internet connection
2. Verify Go is installed: `go version`
3. Try clearing the module cache: `hugo mod clean`
4. Re-download: `hugo mod get -u`

### Port already in use

If port 1313 is busy, use a different port:

```bash
hugo server --port 1314
```
