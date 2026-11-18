const API_BASE = '/api';

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

  async editImage(imageFile, prompt, denoise = 0.65) {
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('prompt', prompt);
    formData.append('denoise', denoise);

    const res = await fetch(`${API_BASE}/edit-image`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error(await res.text());
    // Menerima hasil berupa Blob gambar dari Backend
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },

  async flushVRAM() {
    const res = await fetch(`${API_BASE}/flush`, { method: 'POST' });
    return res.json();
  }
};