import React, { useState, useEffect, useRef } from 'react';
import { 
  Cpu, Image as ImageIcon, MessageSquare, Upload, Sparkles, 
  Trash2, Download, RefreshCw, Terminal, CheckCircle2, AlertCircle, Eye
} from 'lucide-react';
import { apiClient } from './api/client';

export default function App() {
  // Mode: 'image' | 'chat'
  const [mode, setMode] = useState('image');
  
  // Telemetry & Logs buat Troubleshooting
  const [health, setHealth] = useState({ active_vram_owner: 'IDLE', ollama: false, comfyui: false });
  const [logs, setLogs] = useState(['[SYSTEM] Victus AI Studio siap. Menunggu instruksi...']);
  const [loading, setLoading] = useState(false);

  // State Image Editor
  const [sourceFile, setSourceFile] = useState(null);
  const [sourcePreview, setSourcePreview] = useState(null);
  const [resultImage, setResultImage] = useState(null);
  const [imagePrompt, setImagePrompt] = useState('');
  const [denoise, setDenoise] = useState(0.60);
  const [showOriginal, setShowOriginal] = useState(false);
  const fileInputRef = useRef(null);

  // State LLM Chat
  const [chatInput, setChatInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Halo! Mode Chat aktif. Begitu aku selesai menjawab, VRAM RTX 4060 akan langsung dikosongkan otomatis.' }
  ]);

  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString('id-ID', { hour12: false });
    setLogs((prev) => [`[${time}] ${msg}`, ...prev.slice(0, 29)]);
  };

  // Polling status kesehatan container & VRAM tiap 4 detik
  useEffect(() => {
    const checkStatus = async () => {
      try {
        const data = await apiClient.getHealth();
        setHealth(data);
      } catch {
        setHealth({ active_vram_owner: 'OFFLINE', ollama: false, comfyui: false });
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 4000);
    return () => clearInterval(interval);
  }, []);

  // Handler Pilih Gambar
  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSourceFile(file);
    setSourcePreview(URL.createObjectURL(file));
    setResultImage(null);
    addLog(`Gambar dimuat: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
  };

  // Handler Eksekusi Edit Gambar
  const handleEditImage = async (e) => {
    e.preventDefault();
    if (!sourceFile || !imagePrompt.trim() || loading) return;

    setLoading(true);
    addLog(`[VRAM GUARD] Mengalihkan RTX 4060 ke ComfyUI...`);
    addLog(`[PROMPT] "${imagePrompt}" (Denoise: ${denoise})`);

    try {
      const startTime = performance.now();
      const outputUrl = await apiClient.editImage(sourceFile, imagePrompt, denoise);
      const duration = ((performance.now() - startTime) / 1000).toFixed(1);
      
      setResultImage(outputUrl);
      addLog(`[SUCCESS] Selesai dirender dalam ${duration} detik! VRAM dikosongkan kembali.`);
    } catch (err) {
      addLog(`[ERROR] Gagal edit gambar: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handler Kirim Chat LLM
  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || loading) return;

    const userText = chatInput;
    setChatInput('');
    setMessages((prev) => [...prev, { role: 'user', text: userText }]);
    setLoading(true);
    addLog(`[VRAM GUARD] Mengalihkan RTX 4060 ke Ollama (Qwen 2.5)...`);

    try {
      const res = await apiClient.sendChat(userText);
      setMessages((prev) => [...prev, { role: 'assistant', text: res.response }]);
      addLog(`[SUCCESS] Ollama selesai menjawab & keluar dari VRAM.`);
    } catch (err) {
      addLog(`[ERROR] Chat gagal: ${err.message}`);
      setMessages((prev) => [...prev, { role: 'assistant', text: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  // Handler Kuras Paksa VRAM
  const handleFlushVRAM = async () => {
    addLog(`[MANUAL FLUSH] Menguras paksa VRAM RTX 4060...`);
    await apiClient.flushVRAM();
    addLog(`[MANUAL FLUSH] VRAM bersih (0 MB)!`);
  };

  return (
    <div className="min-h-screen flex flex-col bg-zinc-950 text-zinc-100">
      {/* 1. HEADER & MONITOR VRAM RTX 4060 */}
      <header className="border-b border-zinc-800 bg-zinc-900/60 backdrop-blur px-6 py-3 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Cpu size={20} />
          </div>
          <div>
            <h1 className="font-bold text-sm tracking-wide flex items-center gap-2">
              VICTUS AI STUDIO
              <span className="text-[10px] font-mono bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
                RTX 4060 8GB
              </span>
            </h1>
            <p className="text-xs text-zinc-400">Zero-Conflict VRAM Swapping Architecture</p>
          </div>
        </div>

        {/* Switcher Mode: Image vs Chat */}
        <div className="flex bg-zinc-950 p-1 rounded-lg border border-zinc-800">
          <button
            onClick={() => setMode('image')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-xs font-medium transition ${
              mode === 'image' ? 'bg-emerald-500 text-black font-semibold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            <ImageIcon size={15} /> Image Edit Studio
          </button>
          <button
            onClick={() => setMode('chat')}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-xs font-medium transition ${
              mode === 'chat' ? 'bg-emerald-500 text-black font-semibold' : 'text-zinc-400 hover:text-white'
            }`}
          >
            <MessageSquare size={15} /> LLM Chat
          </button>
        </div>

        {/* Status Indikator Engine & Tombol Flush */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-2 bg-zinc-950 px-3 py-1.5 rounded-lg border border-zinc-800">
            <span className="text-zinc-500">VRAM OWNER:</span>
            <span className={`font-bold ${
              health.active_vram_owner === 'IDLE' ? 'text-emerald-400' : 'text-amber-400 animate-pulse'
            }`}>
              {health.active_vram_owner}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-zinc-400">
              {health.ollama ? <CheckCircle2 size={14} className="text-emerald-400" /> : <AlertCircle size={14} className="text-red-400" />}
              Ollama
            </span>
            <span className="flex items-center gap-1 text-zinc-400">
              {health.comfyui ? <CheckCircle2 size={14} className="text-emerald-400" /> : <AlertCircle size={14} className="text-red-400" />}
              ComfyUI
            </span>
          </div>

          <button
            onClick={handleFlushVRAM}
            title="Paksa kosongkan VRAM sekarang"
            className="flex items-center gap-1.5 bg-zinc-800 hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/40 border border-zinc-700 px-3 py-1.5 rounded-lg transition"
          >
            <RefreshCw size={13} /> Flush VRAM
          </button>
        </div>
      </header>

      {/* 2. AREA UTAMA (MAIN WORKSPACE) */}
      <main className="flex-1 max-w-6xl w-full mx-auto p-6 flex flex-col gap-6">
        {mode === 'image' ? (
          /* ================= MODE IMAGE EDIT STUDIO ================= */
          <div className="flex-1 flex flex-col gap-5">
            {/* Kanvas Preview Gambar */}
            <div className="flex-1 min-h-[420px] bg-zinc-900/40 border border-zinc-800 rounded-xl flex items-center justify-center relative overflow-hidden p-4">
              {!sourcePreview ? (
                <div 
                  onClick={() => fileInputRef.current?.click()}
                  className="cursor-pointer flex flex-col items-center gap-3 p-12 border-2 border-dashed border-zinc-700 hover:border-emerald-500/60 rounded-xl transition text-center"
                >
                  <Upload size={36} className="text-emerald-400" />
                  <div>
                    <p className="font-medium text-sm">Klik atau Drag & Drop foto yang mau diedit</p>
                    <p className="text-xs text-zinc-500 mt-1">Mendukung JPG, PNG, WebP (Otomatis dioptimasi untuk VRAM 8GB)</p>
                  </div>
                </div>
              ) : (
                <div className="relative max-h-[480px] flex items-center justify-center">
                  <img
                    src={showOriginal || !resultImage ? sourcePreview : resultImage}
                    alt="Workspace Preview"
                    className={`max-h-[460px] rounded-lg object-contain border border-zinc-800 transition ${
                      loading ? 'opacity-40 blur-[2px]' : 'opacity-100'
                    }`}
                  />

                  {loading && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                      <div className="h-10 w-10 border-4 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs font-mono bg-black/80 px-3 py-1.5 rounded-md border border-zinc-700">
                        RTX 4060 sedang memproses pixel...
                      </span>
                    </div>
                  )}

                  {/* Toolbar Mengambang di Atas Gambar */}
                  <div className="absolute top-3 right-3 flex items-center gap-2">
                    {resultImage && (
                      <>
                        <button
                          onMouseDown={() => setShowOriginal(true)}
                          onMouseUp={() => setShowOriginal(false)}
                          onMouseLeave={() => setShowOriginal(false)}
                          className="bg-black/80 hover:bg-black text-xs px-3 py-1.5 rounded-lg border border-zinc-700 flex items-center gap-1.5"
                        >
                          <Eye size={14} /> Tahan: Lihat Asli
                        </button>
                        <a
                          href={resultImage}
                          download="victus-ai-edit.png"
                          className="bg-emerald-500 hover:bg-emerald-400 text-black font-semibold text-xs px-3 py-1.5 rounded-lg flex items-center gap-1.5"
                        >
                          <Download size={14} /> Simpan
                        </a>
                      </>
                    )}
                    <button
                      onClick={() => { setSourceFile(null); setSourcePreview(null); setResultImage(null); }}
                      className="bg-black/80 hover:bg-red-500/80 p-1.5 rounded-lg border border-zinc-700 transition"
                      title="Ganti gambar"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              )}
              <input ref={fileInputRef} type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
            </div>

            {/* Bar Prompt & Kontrol Denoise ala Gemini */}
            <form onSubmit={handleEditImage} className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl flex flex-col gap-3">
              <div className="flex items-center gap-3">
                <input
                  type="text"
                  value={imagePrompt}
                  onChange={(e) => setImagePrompt(e.target.value)}
                  placeholder="Ketik instruksi edit (contoh: Ganti jaketnya jadi jas hitam elegan, latar malam cyberpunk)..."
                  className="flex-1 bg-zinc-950 border border-zinc-800 focus:border-emerald-500 rounded-lg px-4 py-2.5 text-sm outline-none"
                />
                <button
                  type="submit"
                  disabled={!sourceFile || !imagePrompt.trim() || loading}
                  className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-black font-semibold px-6 py-2.5 rounded-lg text-sm flex items-center gap-2 transition"
                >
                  <Sparkles size={16} /> {loading ? 'Memproses...' : 'Eksekusi Edit'}
                </button>
              </div>

              <div className="flex items-center justify-between text-xs text-zinc-400 pt-1">
                <div className="flex items-center gap-3">
                  <span>Kekuatan Ubahan (Denoise): <strong className="text-emerald-400">{denoise}</strong></span>
                  <input
                    type="range"
                    min="0.20"
                    max="0.95"
                    step="0.05"
                    value={denoise}
                    onChange={(e) => setDenoise(parseFloat(e.target.value))}
                    className="accent-emerald-500 w-36 cursor-pointer"
                  />
                  <span className="text-zinc-500">(0.3 = ubah tipis, 0.65 = ganti objek/baju, 0.85 = rombak total)</span>
                </div>
              </div>
            </form>
          </div>
        ) : (
          /* ================= MODE LLM CHAT ================= */
          <div className="flex-1 flex flex-col bg-zinc-900/40 border border-zinc-800 rounded-xl overflow-hidden">
            <div className="flex-1 p-5 overflow-y-auto space-y-4 max-h-[480px]">
              {messages.map((m, idx) => (
                <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-2xl px-4 py-2.5 rounded-xl text-sm whitespace-pre-wrap ${
                    m.role === 'user' ? 'bg-emerald-500 text-black font-medium' : 'bg-zinc-800 text-zinc-100'
                  }`}>
                    {m.text}
                  </div>
                </div>
              ))}
            </div>
            <form onSubmit={handleSendChat} className="p-3 bg-zinc-900 border-t border-zinc-800 flex gap-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Tanya sesuatu ke Qwen 2.5 7B..."
                className="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-2 text-sm outline-none focus:border-emerald-500"
              />
              <button
                type="submit"
                disabled={loading}
                className="bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 text-black font-semibold px-5 py-2 rounded-lg text-sm"
              >
                Kirim
              </button>
            </form>
          </div>
        )}
      </main>

      {/* 3. DRAWER LOG TROUBLESHOOTING REAL-TIME */}
      <footer className="border-t border-zinc-800 bg-zinc-950 px-6 py-2.5">
        <div className="max-w-6xl mx-auto flex items-start gap-3">
          <div className="flex items-center gap-1.5 text-xs font-mono text-emerald-400 shrink-0 pt-0.5">
            <Terminal size={14} /> LIVE LOG:
          </div>
          <div className="flex-1 h-14 overflow-y-auto font-mono text-[11px] text-zinc-400 space-y-1">
            {logs.map((log, index) => (
              <div key={index} className={index === 0 ? 'text-zinc-200 font-semibold' : ''}>{log}</div>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}