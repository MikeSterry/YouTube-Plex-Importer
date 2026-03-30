# YouTube Plex Importer

A Docker-friendly Flask app with a UI and API that can:
- download a YouTube video as an MKV using the best available video and audio
- optionally parse and merge chapter metadata into the MKV
- optionally download and process poster/background artwork
- queue long-running jobs through Redis + RQ
- edit poster framing interactively with pan, zoom, cover, and contain modes
- output can be linked to a directory Plex uses as a library to automatically import videos

## Features

- Layered architecture:
  - controllers → handlers → services → clients/repositories
- Flask UI with Create and Update tabs
- JSON API for job submission and status lookup
- Redis-backed job queue via RQ worker
- Poster image editor with:
  - live in-browser preview
  - drag-to-pan poster positioning
  - zoom slider
  - cover mode for cropping to fill
  - contain mode for black padding / zooming out
  - server-rendered preview endpoint for final validation
- Directory and file permission normalization to mode `775` and owner/group `1000:1000`
- Docker healthcheck using a Python command

## Project layout

```text
app/
  clients/
  config/
  controllers/
  handlers/
  models/
  repositories/
  services/
  static/
  templates/
scripts/
run.py
worker.py
```

## Configuration

All environment values referenced by Docker Compose are stored in `properties`.

Key settings include:
- `SECRET_KEY`
- `REDIS_URL`
- `RQ_QUEUE_NAME`
- `RQ_DEFAULT_TIMEOUT`
- `INPROGRESS_DIR`
- `OUTPUT_DIR`
- `APP_USER_ID`
- `APP_GROUP_ID`
- `APP_FILE_MODE`
- `APP_DIR_MODE`
- `YTDLP_FORMAT`
- `FFMPEG_BIN`
- `FFPROBE_BIN`
- `MAX_CONTENT_LENGTH`
- `GUNICORN_BIND`
- `GUNICORN_WORKERS`
- `GUNICORN_THREADS`
- `GUNICORN_TIMEOUT`

## Run with Docker Compose

```bash
docker compose up --build
```

The app container exposes the UI and API on port `5001` by default.

## UI workflow

### Create tab
- Enter a YouTube URL
- Optionally provide poster and background URLs
- Optionally paste chapter source text
- If you provide a poster URL, use the poster editor to pan/zoom/crop before submitting

### Update tab
- Select an existing output directory
- Optionally provide a new poster URL, background URL, or chapter text
- Use the same poster editor controls before submitting

## API endpoints

- `POST /api/v1/requests`
- `POST /api/v1/updates`
- `GET /api/v1/outputs`
- `GET /api/v1/jobs/<job_id>`
- `GET /api/v1/artwork/source?url=...`
- `GET /api/v1/artwork/poster-preview?url=...&zoom=1&offset_x=0.5&offset_y=0.5&mode=cover`
- `GET /health`
- `GET /status`

### Example create payload

```json
{
  "youtube_url": "https://www.youtube.com/watch?v=example",
  "poster_url": "https://example.com/poster.jpg",
  "background_url": "https://example.com/background.jpg",
  "chapters_text": "0:00 - Intro\n0:37 - So Alone",
  "poster_zoom": 1.1,
  "poster_offset_x": 0.42,
  "poster_offset_y": 0.36,
  "poster_mode": "cover"
}
```

## Notes

- Poster images are converted to a 2:3 ratio.
- Poster images should ideally be at least `600x900`.
- Background images should ideally already be near `16:9`.
- The poster editor uses a same-origin proxy endpoint so remote artwork can be previewed cleanly in the browser.
- The current version supports poster URL editing. Selecting an existing local poster file from `/output` would be a natural next enhancement.


## Local poster editing

The update workflow can now target an existing poster file already stored inside a selected `/output/<movie>` folder. The UI loads matching `.png`, `.jpg`, and `.jpeg` files into the poster editor so you can pan, zoom, preview, and overwrite the chosen local poster in place.


## Recent update

- Create UI and API now support an optional `output_name` field.
- When provided, that name is used for both the output directory and the MKV filename base.
- Names are sanitized to remain filesystem-safe while preserving readable spaces.
