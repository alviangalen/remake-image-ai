const API_BASE = '/api';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const apiClient = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error('Backend unreachable');
    return res.json();
  },

  async sendChat(prompt) {
    const formData = new FormData();
    formData.append('prompt', prompt);
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async sendChatStream(prompt, onToken) {
    const formData = new FormData();
    formData.append('prompt', prompt);
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    if (!res.body) throw new Error('Browser tidak mendukung response streaming.');

    const reader = res.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let fullText = '';

    const processLine = (rawLine) => {
      const line = rawLine.trim();
      if (!line) return;
      const chunk = JSON.parse(line);
      if (chunk.error) throw new Error(chunk.error);
      if (chunk.response) {
        fullText += chunk.response;
        if (onToken) onToken(chunk.response, fullText);
      }
    };

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          processLine(line);
        }
      }
      buffer += decoder.decode();
      if (buffer.trim()) {
        processLine(buffer);
      }
    } finally {
      reader.releaseLock();
    }

    return { response: fullText };
  },

  async editImageWithProgress(imageFile, prompt, denoise = 1.0, guidance = 2.5, seed = null, onProgress = null) {
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('prompt', prompt);
    formData.append('denoise', denoise);
    formData.append('guidance', guidance);
    if (seed !== null && seed !== '' && !Number.isNaN(Number(seed))) {
      formData.append('seed', String(seed));
    }

    const startRes = await fetch(`${API_BASE}/edit-image/jobs`, {
      method: 'POST',
      body: formData,
    });
    if (!startRes.ok) throw new Error(await startRes.text());
    const { job_id: jobId } = await startRes.json();

    let consecutiveErrors = 0;
    while (true) {
      await sleep(700);
      let statusRes;
      try {
        statusRes = await fetch(`${API_BASE}/edit-image/jobs/${jobId}`);
      } catch (err) {
        consecutiveErrors += 1;
        if (consecutiveErrors > 10) throw err;
        continue;
      }

      if (!statusRes.ok) {
        consecutiveErrors += 1;
        if (consecutiveErrors > 5) {
          throw new Error(await statusRes.text());
        }
        continue;
      }
      consecutiveErrors = 0;

      const status = await statusRes.json();
      if (onProgress) onProgress(status);

      if (status.status === 'failed') {
        throw new Error(status.error || 'Gagal memproses gambar');
      }
      if (status.status === 'completed') {
        const resultRes = await fetch(`${API_BASE}/edit-image/jobs/${jobId}/result`);
        if (!resultRes.ok) throw new Error(await resultRes.text());
        const blob = await resultRes.blob();
        return {
          url: URL.createObjectURL(blob),
          seed: resultRes.headers.get('X-Seed') || status.seed,
          prompt: resultRes.headers.get('X-Prompt') || status.prompt,
          elapsed: resultRes.headers.get('X-Elapsed-Seconds') || status.elapsed_seconds,
        };
      }
    }
  },

  async editImage(imageFile, prompt, denoise = 1.0, guidance = 2.5, seed = null) {
    return this.editImageWithProgress(imageFile, prompt, denoise, guidance, seed, null);
  },

  async flushVRAM() {
    const res = await fetch(`${API_BASE}/flush`, { method: 'POST' });
    return res.json();
  },
};
