# Quick Start

## Prerequisites

- Python 3.11 or later
- A [Flickr API key](https://www.flickr.com/services/apps/create/)

## Installation

```bash
git clone https://github.com/maximusmaximus/flickrtag.git
cd flickrtag
uv pip install -e ".[dev]"
```

## Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` with your Flickr API credentials:

```env
FLICKR_API_KEY=your_api_key_here
FLICKR_API_SECRET=your_api_secret_here
```

## Usage

### Step 1: Authenticate

```bash
flickr-autotagger auth
```

This opens your browser for Flickr OAuth authorization. You'll paste back a verification code.

### Step 2: Sync Metadata

```bash
flickr-autotagger sync
```

Fetches all your photo metadata from Flickr into a local SQLite database.

### Step 3: Download Images

```bash
flickr-autotagger download --concurrency 4
```

Downloads original-resolution images. This is resumable — stop and restart at any time.

### Step 4: AI Tagging

```bash
flickr-autotagger tag
```

Runs CLIP inference on all downloaded images. The model is downloaded once and cached.

### Step 5: Review Tags

```bash
flickr-autotagger review
```

Interactively review predicted tags. You can approve all, select specific tags, or skip.

### Step 6: Push to Flickr

```bash
flickr-autotagger push --dry-run   # Preview
flickr-autotagger push             # Execute
```

### Step 7: Export

```bash
flickr-autotagger export --format json --output tags.json
flickr-autotagger export --format csv --output tags.csv
flickr-autotagger export --format xmp
```
