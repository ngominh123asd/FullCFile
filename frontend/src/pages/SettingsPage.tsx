import { useState, useEffect } from 'react'
import { Server, Sliders, ExternalLink, Check, Copy, Terminal } from 'lucide-react'
import { Button } from '../components/ui/button'
import { systemApi, API_PUBLIC_URL } from '../lib/api'
import { copyText } from '../lib/utils'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const [backendOnline, setBackendOnline] = useState(true)
  const [defaultOcrLang, setDefaultOcrLang] = useState(() => localStorage.getItem('fileforge_default_ocr_lang') || 'vi')
  const [autoDownload, setAutoDownload] = useState(() => localStorage.getItem('fileforge_auto_download') === 'true')
  const [copiedKey, setCopiedKey] = useState(false)

  useEffect(() => {
    systemApi.checkHealth().then((res) => setBackendOnline(res.online))
  }, [])

  const handleCopyApiUrl = async () => {
    const ok = await copyText(API_PUBLIC_URL)
    if (ok) {
      setCopiedKey(true)
      toast.success('Đã sao chép Base URL!')
      setTimeout(() => setCopiedKey(false), 2000)
    }
  }

  const toggleAutoDownload = () => {
    const nextVal = !autoDownload
    setAutoDownload(nextVal)
    localStorage.setItem('fileforge_auto_download', String(nextVal))
    if (nextVal) {
      toast.success('Đã BẬT tự động tải xuống sau khi chuyển đổi!')
    } else {
      toast('Đã TẮT tự động tải xuống', { icon: 'ℹ️' })
    }
  }

  const handleSelectOcrLang = (langId: string, label: string) => {
    setDefaultOcrLang(langId)
    localStorage.setItem('fileforge_default_ocr_lang', langId)
    toast.success(`Đã lưu ngôn ngữ mặc định: ${label}`)
  }

  return (
    <div className="space-y-5 sm:space-y-6 max-w-4xl min-w-0 max-w-full overflow-hidden">
      {/* Header Banner - ZZZ Device Frame (Screenshot 1 & 3) */}
      <div className="zzz-device-frame p-5 sm:p-6 space-y-1">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#B8E900]" />
          <h2 className="text-lg sm:text-xl font-bold font-tech uppercase tracking-wider text-white">
            CÀI ĐẶT HỆ THỐNG // CONFIG
          </h2>
        </div>
        <p className="text-xs font-mono text-[#9CA3AF] pl-4">
          Cấu hình tham số mặc định của AST Engine và giám sát telemetry máy chủ
        </p>
      </div>

      {/* System Telemetry Plate */}
      <div className="zzz-device-frame p-5 sm:p-6 space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-[#282B37]">
          <div className="w-7 h-7 rounded-lg bg-[#222530] border border-[#2E313E] flex items-center justify-center text-[#B8E900]">
            <Server className="w-3.5 h-3.5" />
          </div>
          <h3 className="text-sm font-bold font-tech uppercase tracking-wider text-white">
            THÔNG SỐ KỸ THUẬT MÁY CHỦ
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          <div className="p-3.5 rounded-xl bg-[#222530] border border-[#2E313E]">
            <p className="text-[10px] font-mono text-[#6B7280]">TRẠNG THÁI FASTAPI</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`w-2 h-2 rounded-full ${backendOnline ? 'bg-[#B8E900] animate-pulse shadow-[0_0_8px_#B8E900]' : 'bg-[#FF3355]'}`} />
              <p className="text-xs font-mono font-bold text-white">{backendOnline ? 'CONNECTED' : 'DISCONNECTED'}</p>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-[#222530] border border-[#2E313E]">
            <p className="text-[10px] font-mono text-[#6B7280]">API PROTOCOL</p>
            <p className="text-xs font-mono font-bold text-[#B8E900] mt-1">REST / JSON (v1)</p>
          </div>

          <div className="p-3.5 rounded-xl bg-[#222530] border border-[#2E313E]">
            <p className="text-[10px] font-mono text-[#6B7280]">XỬ LÝ ĐA LUỒNG</p>
            <p className="text-xs font-mono font-bold text-white mt-1">Asynchronous FastAPI</p>
          </div>
        </div>
      </div>

      {/* Engine Defaults */}
      <div className="zzz-device-frame p-5 sm:p-6 space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-[#282B37]">
          <div className="w-7 h-7 rounded-lg bg-[#222530] border border-[#2E313E] flex items-center justify-center text-[#B8E900]">
            <Sliders className="w-3.5 h-3.5" />
          </div>
          <h3 className="text-sm font-bold font-tech uppercase tracking-wider text-white">
            TÙY CHỌN MẶC ĐỊNH
          </h3>
        </div>

        <div className="space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-[#222530] border border-[#2E313E]">
            <div>
              <p className="text-xs font-bold font-tech uppercase text-white">Ngôn ngữ OCR ưu tiên</p>
              <p className="text-[11px] font-mono text-[#9CA3AF]">Tự động áp dụng cho các tác vụ tải ảnh lên mới</p>
            </div>
            <div className="flex gap-2 overflow-x-auto custom-scrollbar pb-1 sm:pb-0">
              {[
                { id: 'vi', label: 'Tiếng Việt' },
                { id: 'en', label: 'English' },
                { id: 'auto', label: 'Tự động' },
              ].map((l) => (
                <button
                  key={l.id}
                  onClick={() => handleSelectOcrLang(l.id, l.label)}
                  className={`px-3 py-1.5 rounded-full text-xs font-tech font-bold uppercase transition-all whitespace-nowrap ${
                    defaultOcrLang === l.id
                      ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                      : 'bg-[#181A22] text-[#9CA3AF] hover:text-white border border-[#282B37]'
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-[#222530] border border-[#2E313E]">
            <div className="pr-2">
              <p className="text-xs font-bold font-tech uppercase text-white">Tự động tải xuống sau khi chuyển đổi xong</p>
              <p className="text-[11px] font-mono text-[#9CA3AF]">Kích hoạt tải file tức thì khi status chuyển sang Hoàn thành</p>
            </div>

            {/* ZZZ Tactile Toggle Switch */}
            <button
              type="button"
              role="switch"
              aria-checked={autoDownload}
              onClick={toggleAutoDownload}
              className={`relative inline-flex h-7 w-12 flex-shrink-0 cursor-pointer rounded-full border border-[#323646] transition-colors duration-200 ease-in-out focus:outline-none ${
                autoDownload ? 'bg-[#B8E900] shadow-[0_0_12px_rgba(184,233,0,0.4)]' : 'bg-[#181A22]'
              }`}
            >
              <span
                aria-hidden="true"
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full shadow-md transition duration-200 ease-in-out mt-0.5 ${
                  autoDownload ? 'translate-x-6 bg-[#0C0D10]' : 'translate-x-1 bg-[#6B7280]'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* API Credentials */}
      <div className="zzz-device-frame p-5 sm:p-6 space-y-4">
        <div className="flex items-center gap-2.5 pb-3 border-b border-[#282B37]">
          <div className="w-7 h-7 rounded-lg bg-[#222530] border border-[#2E313E] flex items-center justify-center text-[#B8E900]">
            <Terminal className="w-3.5 h-3.5" />
          </div>
          <h3 className="text-sm font-bold font-tech uppercase tracking-wider text-white">
            API INTEGRATION
          </h3>
        </div>

        <div className="p-3.5 rounded-xl bg-[#222530] border border-[#2E313E] flex flex-col sm:flex-row sm:items-center justify-between gap-3 min-w-0">
          <div className="min-w-0 flex-1">
            <p className="text-[10px] font-mono text-[#6B7280]">API ROOT ENDPOINT</p>
            <p className="text-xs font-mono text-[#B8E900] mt-0.5 truncate select-all" title={API_PUBLIC_URL}>
              {API_PUBLIC_URL}
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleCopyApiUrl}
            className="text-xs h-8 sm:h-9 px-3 self-start sm:self-auto flex-shrink-0"
          >
            {copiedKey ? <Check className="w-3.5 h-3.5 text-[#B8E900] mr-1" /> : <Copy className="w-3.5 h-3.5 mr-1" />}
            {copiedKey ? 'ĐÃ SAO CHÉP' : 'SAO CHÉP URL'}
          </Button>
        </div>

        <div className="flex justify-start sm:justify-end pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open(API_PUBLIC_URL.replace(/\/api\/v1$/, '/docs'), '_blank')}
            className="w-full sm:w-auto text-xs h-9 justify-center"
          >
            <ExternalLink className="w-3.5 h-3.5 mr-1" /> Mở Swagger Interactive Docs
          </Button>
        </div>
      </div>
    </div>
  )
}
