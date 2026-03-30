document.querySelectorAll('.tab-button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.tab-button').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    const target = document.getElementById(button.dataset.tab);
    if (target) target.classList.add('active');
  });
});

class PosterEditor {
  constructor(root) {
    this.root = root;
    this.form = root.closest('form');
    this.formMode = this.form.dataset.formMode || 'create';
    this.urlInput = this.form.querySelector('[data-poster-url]');
    this.outputSelect = this.form.querySelector('[data-output-name]');
    this.canvas = root.querySelector('[data-poster-canvas]');
    this.context = this.canvas.getContext('2d');
    this.sourceTypeInput = root.querySelector('[data-poster-source-type]');
    this.localFileInput = root.querySelector('[data-poster-local-file]');
    this.localRow = root.querySelector('[data-poster-local-row]');
    this.modeInput = root.querySelector('[data-poster-mode]');
    this.zoomInput = root.querySelector('[data-poster-zoom]');
    this.offsetXInput = root.querySelector('[data-poster-offset-x]');
    this.offsetYInput = root.querySelector('[data-poster-offset-y]');
    this.hiddenZoom = root.querySelector('[data-poster-hidden-zoom]');
    this.hiddenOffsetX = root.querySelector('[data-poster-hidden-offset-x]');
    this.hiddenOffsetY = root.querySelector('[data-poster-hidden-offset-y]');
    this.hiddenMode = root.querySelector('[data-poster-hidden-mode]');
    this.message = root.querySelector('[data-poster-message]');
    this.refreshButton = root.querySelector('[data-poster-preview]');
    this.resetButton = root.querySelector('[data-poster-reset]');
    this.dragging = false;
    this.configureSourceOptions();
    this.bindEvents();
    this.drawEmpty();
  }

  configureSourceOptions() {
    if (this.formMode === 'create') {
      this.sourceTypeInput.value = 'url';
      this.sourceTypeInput.disabled = true;
      this.localRow.style.display = 'none';
      return;
    }
    this.toggleSourceFields();
  }

  bindEvents() {
    this.urlInput.addEventListener('change', () => this.loadSource());
    if (this.sourceTypeInput) this.sourceTypeInput.addEventListener('change', () => this.onSourceTypeChanged());
    if (this.localFileInput) this.localFileInput.addEventListener('change', () => this.loadSource());
    if (this.outputSelect) this.outputSelect.addEventListener('change', () => this.onOutputChanged());
    this.zoomInput.addEventListener('input', () => this.syncAndRender());
    this.offsetXInput.addEventListener('input', () => this.syncAndRender());
    this.offsetYInput.addEventListener('input', () => this.syncAndRender());
    this.modeInput.addEventListener('change', () => this.syncAndRender());
    this.refreshButton.addEventListener('click', () => this.fetchServerPreview());
    this.resetButton.addEventListener('click', () => this.reset());
    this.canvas.addEventListener('mousedown', (event) => this.startDrag(event));
    window.addEventListener('mousemove', (event) => this.onDrag(event));
    window.addEventListener('mouseup', () => this.stopDrag());
  }

  reset() {
    this.zoomInput.value = '1';
    this.offsetXInput.value = '0.5';
    this.offsetYInput.value = '0.5';
    this.modeInput.value = 'cover';
    this.syncAndRender();
  }

  async onOutputChanged() {
    if (this.formMode !== 'update') return;
    await this.loadLocalPosterOptions();
    this.loadSource();
  }

  onSourceTypeChanged() {
    this.toggleSourceFields();
    this.loadSource();
  }

  toggleSourceFields() {
    const useLocal = this.sourceTypeInput.value === 'local';
    this.localRow.style.display = useLocal ? 'flex' : 'none';
    this.urlInput.closest('label').style.display = useLocal ? 'none' : 'flex';
  }

  async loadLocalPosterOptions() {
    const outputName = (this.outputSelect?.value || '').trim();
    this.localFileInput.innerHTML = '<option value="">Select a local poster file</option>';
    if (!outputName) return;
    const response = await fetch(`/api/v1/outputs/${encodeURIComponent(outputName)}/poster-files`);
    const payload = await response.json();
    (payload.poster_files || []).forEach((fileName) => {
      const option = document.createElement('option');
      option.value = fileName;
      option.textContent = fileName;
      this.localFileInput.appendChild(option);
    });
  }

  startDrag(event) {
    if (!this.image) return;
    this.dragging = true;
    this.lastPoint = { x: event.offsetX, y: event.offsetY };
  }

  onDrag(event) {
    if (!this.dragging || !this.image) return;
    const bounds = this.canvas.getBoundingClientRect();
    const current = { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
    const deltaX = current.x - this.lastPoint.x;
    const deltaY = current.y - this.lastPoint.y;
    this.lastPoint = current;
    const sensitivity = 0.0025;
    this.offsetXInput.value = this.clamp(parseFloat(this.offsetXInput.value) + deltaX * sensitivity, 0, 1);
    this.offsetYInput.value = this.clamp(parseFloat(this.offsetYInput.value) + deltaY * sensitivity, 0, 1);
    this.syncAndRender();
  }

  stopDrag() {
    this.dragging = false;
  }

  async loadSource() {
    const descriptor = this.getSourceDescriptor();
    if (!descriptor) {
      this.image = null;
      this.drawEmpty();
      this.message.textContent = 'No poster loaded yet.';
      return;
    }
    this.message.textContent = 'Loading poster editor...';
    const image = new Image();
    image.onload = () => {
      this.image = image;
      this.syncAndRender();
      this.message.textContent = `Loaded ${image.width}x${image.height}.`;
    };
    image.onerror = () => {
      this.image = null;
      this.drawEmpty();
      this.message.textContent = 'Unable to load poster image.';
    };
    image.src = descriptor.sourceUrl;
  }

  getSourceDescriptor() {
    const sourceType = this.sourceTypeInput?.value || 'url';
    if (sourceType === 'local') {
      const outputName = (this.outputSelect?.value || '').trim();
      const fileName = (this.localFileInput?.value || '').trim();
      if (!outputName || !fileName) return null;
      return {
        previewUrl: `/api/v1/artwork/local-poster-preview?output_name=${encodeURIComponent(outputName)}&file=${encodeURIComponent(fileName)}`,
        sourceUrl: `/api/v1/artwork/local-source?output_name=${encodeURIComponent(outputName)}&file=${encodeURIComponent(fileName)}`,
      };
    }
    const url = (this.urlInput?.value || '').trim();
    if (!url) return null;
    return {
      previewUrl: `/api/v1/artwork/poster-preview?url=${encodeURIComponent(url)}`,
      sourceUrl: `/api/v1/artwork/source?url=${encodeURIComponent(url)}`,
    };
  }

  syncAndRender() {
    this.hiddenZoom.value = this.zoomInput.value;
    this.hiddenOffsetX.value = this.offsetXInput.value;
    this.hiddenOffsetY.value = this.offsetYInput.value;
    this.hiddenMode.value = this.modeInput.value;
    this.renderClientPreview();
  }

  drawEmpty() {
    this.context.fillStyle = '#111827';
    this.context.fillRect(0, 0, this.canvas.width, this.canvas.height);
    this.context.strokeStyle = '#475569';
    this.context.strokeRect(1, 1, this.canvas.width - 2, this.canvas.height - 2);
    this.context.fillStyle = '#cbd5e1';
    this.context.font = '16px sans-serif';
    this.context.textAlign = 'center';
    this.context.fillText('Poster preview', this.canvas.width / 2, this.canvas.height / 2);
  }

  renderClientPreview() {
    if (!this.image) {
      this.drawEmpty();
      return;
    }
    const mode = this.modeInput.value;
    const zoom = Math.max(parseFloat(this.zoomInput.value), 0.01);
    const offsetX = this.clamp(parseFloat(this.offsetXInput.value), 0, 1);
    const offsetY = this.clamp(parseFloat(this.offsetYInput.value), 0, 1);
    const canvasWidth = this.canvas.width;
    const canvasHeight = this.canvas.height;
    const baseScale = mode === 'contain'
      ? Math.min(canvasWidth / this.image.width, canvasHeight / this.image.height)
      : Math.max(canvasWidth / this.image.width, canvasHeight / this.image.height);
    const effectiveZoom = mode === 'contain' ? zoom : Math.max(zoom, 1);
    const width = this.image.width * baseScale * effectiveZoom;
    const height = this.image.height * baseScale * effectiveZoom;
    const x = (canvasWidth - width) * offsetX;
    const y = (canvasHeight - height) * offsetY;
    this.context.fillStyle = '#000';
    this.context.fillRect(0, 0, canvasWidth, canvasHeight);
    this.context.drawImage(this.image, x, y, width, height);
  }

  async fetchServerPreview() {
    const descriptor = this.getSourceDescriptor();
    if (!descriptor) {
      this.message.textContent = 'Choose a poster URL or local poster file first.';
      return;
    }
    const params = new URLSearchParams({
      zoom: this.zoomInput.value,
      offset_x: this.offsetXInput.value,
      offset_y: this.offsetYInput.value,
      mode: this.modeInput.value,
    });
    const image = new Image();
    image.onload = () => {
      this.image = image;
      this.renderClientPreview();
      this.message.textContent = `Server preview refreshed at ${image.width}x${image.height}.`;
    };
    image.onerror = () => {
      this.message.textContent = 'Unable to render server preview.';
    };
    image.src = `${descriptor.previewUrl}&${params.toString()}`;
  }

  clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }
}

document.querySelectorAll('[data-poster-editor]').forEach((element) => new PosterEditor(element));
