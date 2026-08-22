# Configuration

All settings are loaded from a `.env` file in the project root, or from environment variables.

## Required Settings

| Variable | Description |
|----------|-------------|
| `FLICKR_API_KEY` | Your Flickr API key. Get one at [flickr.com/services/apps/create](https://www.flickr.com/services/apps/create/). |
| `FLICKR_API_SECRET` | Your Flickr API secret (provided with the key). |

## Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `FLICKR_USER_ID` | *(auto-detected)* | Your Flickr NSID. If not set, it's detected automatically after OAuth login. |
| `DATA_DIR` | `~/.flickr-autotagger` | Base directory for the SQLite database and downloaded images. |
| `CLIP_MODEL` | `clip-vit-base-patch32` | The CLIP model variant to use. |
| `TAG_THRESHOLD` | `0.25` | Minimum confidence score (0.0–1.0) for a tag to be included in predictions. Lower = more tags, higher = more precise. |
| `MAX_TAGS_PER_PHOTO` | `15` | Maximum number of predicted tags per photo. |
| `DOWNLOAD_CONCURRENCY` | `4` | Number of parallel image downloads. |
| `TAG_MERGE_STRATEGY` | `merge` | How to handle existing tags when pushing. `merge` appends new tags alongside existing ones. `replace` overwrites all tags. |

## Custom Tag Vocabulary

By default, flickr-autotagger uses a built-in vocabulary of ~200 tags across 13 categories. You can provide your own:

```yaml
# custom-tags.yml
tags:
  - urban exploration
  - astrophotography
  - macro insects
  - my dog Biscuit
```

Use it with:

```bash
flickr-autotagger tag --custom-tags custom-tags.yml
```

## Data Directory Structure

```
~/.flickr-autotagger/
├── state.db          # SQLite database tracking all state
├── auth_token/       # Cached OAuth token
└── images/           # Downloaded original images
    ├── 12345678.jpg
    ├── 12345679.jpg
    └── ...
```
