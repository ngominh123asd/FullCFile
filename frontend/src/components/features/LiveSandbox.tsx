import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileText, Image as ImageIcon, Table as TableIcon, ArrowRight, CheckCircle2, Sparkles, Check } from 'lucide-react'
import { useI18n } from '../../lib/i18n'

const DEMO_PRESETS = [
  {
    id: 'md_docx',
    label: 'Markdown ➔ DOCX Chuẩn',
    icon: FileText,
    badge: 'DOC FORMATTER',
    sourceTitle: 'sample_spec.md (Markdown Gốc)',
    targetTitle: 'output_academic.docx (DOCX Hoàn Thiện)',
    source: `# 1. KIẾN TRÚC HỆ THỐNG FILEFORGE
> Tài liệu kỹ thuật chuẩn mực cao

## 1.1 Khái Niệm Cốt Lõi
Hệ thống xử lý tài liệu phân tán ứng dụng **PaddleOCR PP-Structure** và **Pandoc Engine**.

### Danh Sách Tham Số
* Chuẩn hóa phông chữ: \`Times New Roman / Inter\`
* Độ giãn dòng: \`1.25x\`
* Khổ giấy: \`A4 tiêu chuẩn\``,
    rendered: {
      type: 'document',
      title: '1. KIẾN TRÚC HỆ THỐNG FILEFORGE',
      subtitle: 'Tài liệu kỹ thuật chuẩn mực cao (Academic Format)',
      section: '1.1 Khái Niệm Cốt Lõi',
      body: 'Hệ thống xử lý tài liệu phân tán ứng dụng PaddleOCR PP-Structure và Pandoc Engine với tính năng bảo toàn 100% cấu trúc Heading, Paragraphs, Bảng biểu và Chú thích chân trang.',
      table: [
        ['Tham Số Kỹ Thuật', 'Giá Trị Thiết Lập', 'Trạng Thái'],
        ['Font Family', 'Times New Roman / Inter', 'Đã Áp Dụng'],
        ['Line Height', '1.25x Tự Động Cân Chỉnh', 'Đạt Chuẩn'],
        ['Page Setup', 'A4 (210 x 297 mm)', 'Khớp Khung'],
      ],
    },
  },
  {
    id: 'ocr_image',
    label: 'Ảnh ➔ OCR Tiếng Việt',
    icon: ImageIcon,
    badge: 'PADDLE OCR PP-STRUCTURE',
    sourceTitle: 'invoice_scan_sample.png (Ảnh Hóa Đơn Thực Tế)',
    targetTitle: 'ocr_extracted.json & Text',
    rendered: {
      type: 'ocr',
      confidence: '99.4%',
      language: 'Tiếng Việt (Có Dấu UTF-8)',
      extracted_fields: [
        { label: 'Đơn Vị Xuất Hóa Đơn', value: 'CÔNG TY TNHH CÔNG NGHỆ FILEFORGE' },
        { label: 'Mã Số Thuế', value: '0318928192' },
        { label: 'Số Hóa Đơn', value: 'HD-2026/08-9812' },
        { label: 'Ngày Lập Hóa Đơn', value: '17/08/2026 - 14:32:10' },
        { label: 'Tổng Tiền Thanh Toán', value: '8,200,000 VNĐ' },
        { label: 'Trạng Thái Xác Thực', value: 'Chữ Ký Số Hợp Lệ (SHA-256)' },
      ],
      rawText: `CÔNG TY TNHH CÔNG NGHỆ FILEFORGE
Địa chỉ: Tầng 12, Tòa nhà Công Nghệ Cao, Q.1, TP.HCM
Mã số thuế: 0318928192
HÓA ĐƠN BÁN HÀNG & DỊCH VỤ CLOUD
Số: HD-2026/08-9812 • Ngày: 17/08/2026

1. Gói PaddleOCR PP-Structure v2.8 (1 Năm)  x1   5,000,000 đ
2. Máy Chủ Xử Lý Redis Caching Cluster     x1   3,200,000 đ
------------------------------------------------------------
TỔNG CỘNG TIỀN THANH TOÁN (ĐÃ GỒM VAT):        8,200,000 đ
(Bằng chữ: Tám triệu hai trăm nghìn đồng chẵn)`,
    },
  },
  {
    id: 'csv_json',
    label: 'Bảng Tính CSV ➔ JSON Matrix',
    icon: TableIcon,
    badge: 'DATA MATRIX',
    sourceTitle: 'metrics_2026.csv (CSV Gốc)',
    targetTitle: 'schema_validated.json (JSON Cấu Trúc)',
    source: `id,service_name,latency_ms,status,uptime
1,PaddleOCR Vision,18.4,operational,99.98%
2,Pandoc Engine,42.1,operational,99.95%
3,Redis Cache Pool,2.1,operational,100%`,
    rendered: {
      type: 'json',
      json: JSON.stringify(
        {
          version: '2.0.0',
          generated_at: '2026-08-17T16:40:00Z',
          dataset_name: 'metrics_2026',
          record_count: 3,
          records: [
            { id: 1, service_name: 'PaddleOCR Vision', latency_ms: 18.4, status: 'operational', uptime: '99.98%' },
            { id: 2, service_name: 'Pandoc Engine', latency_ms: 42.1, status: 'operational', uptime: '99.95%' },
            { id: 3, service_name: 'Redis Cache Pool', latency_ms: 2.1, status: 'operational', uptime: '100%' },
          ],
        },
        null,
        2
      ),
    },
  },
]

export default function LiveSandbox() {
  const { t } = useI18n()
  const [activePresetIndex, setActivePresetIndex] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const [simulatedProgress, setSimulatedProgress] = useState(100)

  const activePreset = DEMO_PRESETS[activePresetIndex]

  const runSimulation = () => {
    setIsRunning(true)
    setSimulatedProgress(0)

    const interval = setInterval(() => {
      setSimulatedProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval)
          setIsRunning(false)
          return 100
        }
        return prev + 25
      })
    }, 120)
  }

  return (
    <div id="sandbox" className="w-full zzz-device-frame p-5 sm:p-7 shadow-2xl">
      {/* Sandbox Header */}
      <div className="flex flex-col gap-4 pb-5 border-b border-[#282B37]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#222530] text-[#B8E900] text-xs font-mono font-bold border border-[#2E313E] mb-2">
              <Sparkles className="w-3.5 h-3.5" />
              <span>INTERACTIVE CONVERSION LAB</span>
            </div>
            <h3 className="text-xl md:text-2xl font-bold font-tech uppercase tracking-wider text-white">{t('sandbox.title')}</h3>
            <p className="text-xs md:text-sm font-mono text-[#9CA3AF] mt-1">{t('sandbox.desc')}</p>
          </div>
        </div>

        {/* 3 Tabs on a Single Horizontal Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 bg-[#14151C] p-1.5 rounded-xl border border-[#282B37] w-full mt-2">
          {DEMO_PRESETS.map((preset, idx) => {
            const Icon = preset.icon
            const isActive = activePresetIndex === idx
            return (
              <button
                key={preset.id}
                onClick={() => {
                  setActivePresetIndex(idx)
                  runSimulation()
                }}
                className={`flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-tech font-bold uppercase tracking-wider transition-all text-center ${isActive
                  ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                  : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
                  }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{preset.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-5">
        {/* Left: Input Source */}
        <div className="flex flex-col rounded-xl bg-[#14151C] border border-[#282B37] overflow-hidden">
          <div className="p-3 bg-[#181A22] border-b border-[#282B37] flex items-center justify-between text-xs font-mono">
            <span className="text-white flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#FF5E00]" />
              {activePreset.sourceTitle}
            </span>
            <span className="text-[#6B7280]">INPUT</span>
          </div>

          {/* Conditional Input Rendering */}
          {activePreset.id === 'ocr_image' ? (
            <div className="p-4 flex-1 overflow-auto max-h-[360px] bg-[#101116] relative flex items-center justify-center">
              <div className="relative w-full max-w-sm bg-[#FAF8F5] text-[#1E293B] rounded-xl p-5 shadow-2xl border border-[#CBD5E1] text-[11px] font-mono select-none overflow-hidden">
                {/* Laser Scanning Bar Animation */}
                {isRunning && (
                  <motion.div
                    initial={{ top: '0%' }}
                    animate={{ top: '100%' }}
                    transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
                    className="absolute left-0 right-0 h-1 bg-[#B8E900] shadow-[0_0_12px_#B8E900] z-20"
                  />
                )}

                {/* OCR Bounding Boxes */}
                <div className="absolute top-4 left-4 right-4 h-8 border border-dashed border-[#B8E900] bg-[#B8E900]/10 rounded pointer-events-none" />
                <div className="absolute top-24 left-4 right-4 h-16 border border-dashed border-emerald-500/60 bg-emerald-500/5 rounded pointer-events-none" />

                {/* Invoice Header */}
                <div className="text-center pb-3 border-b border-slate-300">
                  <div className="flex items-center justify-center gap-2 mb-1">
                    <div className="w-5 h-5 rounded bg-[#101116] text-[#B8E900] font-bold flex items-center justify-center text-[10px]">
                      Z
                    </div>
                    <span className="font-bold text-xs tracking-tight text-[#0F172A]">
                      CÔNG TY TNHH CÔNG NGHỆ FILEFORGE
                    </span>
                  </div>
                  <p className="text-[9px] text-[#64748B]">Tầng 12, Tòa nhà Công Nghệ Cao, Q.1, TP.HCM</p>
                  <p className="text-[9px] text-[#64748B]">MST: 0318928192 • Hotline: 1900 8899</p>
                  <div className="mt-2 py-0.5 px-2 inline-block bg-[#E2E8F0] rounded font-bold text-[10px] text-[#0F172A]">
                    HÓA ĐƠN ĐIỆN TỬ
                  </div>
                  <p className="text-[9px] text-[#64748B] mt-1">Số: HD-2026/08-9812 • Ngày: 17/08/2026</p>
                </div>

                {/* Itemized Table */}
                <div className="py-3 border-b border-slate-300">
                  <div className="flex justify-between font-bold text-[10px] pb-1 border-b border-slate-200">
                    <span>Dịch Vụ</span>
                    <span>Số Tiền</span>
                  </div>
                  <div className="flex justify-between py-1 text-[10px]">
                    <span>1. PaddleOCR Pro v2.8 (1 Năm)</span>
                    <span className="font-semibold">5,000,000 đ</span>
                  </div>
                  <div className="flex justify-between py-1 text-[10px]">
                    <span>2. Redis Caching Cluster (RAM)</span>
                    <span className="font-semibold">3,200,000 đ</span>
                  </div>
                </div>

                {/* Total */}
                <div className="pt-2 flex justify-between items-center font-bold text-xs text-[#0F172A]">
                  <span>TỔNG CỘNG (VAT):</span>
                  <span className="text-[#0284C7] text-sm">8,200,000 đ</span>
                </div>

                {/* Stamp & Barcode */}
                <div className="mt-3 pt-2 border-t border-dashed border-slate-300 flex items-center justify-between text-[9px] text-[#64748B]">
                  <div>
                    <span className="inline-flex items-center gap-1 text-emerald-600 font-semibold">
                      <Check className="w-3 h-3" /> ĐÃ KÝ ĐIỆN TỬ
                    </span>
                    <p className="text-[8px]">SHA256: 8f9a...bc41</p>
                  </div>
                  <div className="flex flex-col items-center">
                    <div className="w-10 h-10 bg-slate-900 text-white flex items-center justify-center text-[7px] font-mono rounded">
                      [QR-CODE]
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 flex-1 font-mono text-xs text-[#9CA3AF] overflow-auto max-h-[360px] whitespace-pre-wrap leading-relaxed custom-scrollbar">
              {activePreset.source}
            </div>
          )}

          <div className="p-3 bg-[#181A22] border-t border-[#282B37] flex items-center justify-between text-xs font-mono">
            <span className="text-[11px] font-mono text-[#6B7280]">Định dạng: {activePreset.badge}</span>
            <span className="text-[11px] font-mono text-[#B8E900] flex items-center gap-1.5 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900] animate-pulse" />
              TỰ ĐỘNG CHUYỂN ĐỔI THỜI GIAN THỰC
            </span>
          </div>
        </div>

        {/* Right: Rendered Output */}
        <div className="flex flex-col rounded-xl bg-[#14151C] border border-[#282B37] overflow-hidden">
          <div className="p-3 bg-[#181A22] border-b border-[#282B37] flex items-center justify-between text-xs font-mono">
            <span className="text-white flex items-center gap-2 font-bold font-tech uppercase">
              <span className="w-2 h-2 rounded-full bg-[#B8E900] animate-pulse" />
              {activePreset.targetTitle}
            </span>
            <span className="text-[#B8E900] font-bold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> 100% READY
            </span>
          </div>

          {/* Render Area */}
          <div className="p-5 flex-1 overflow-auto max-h-[360px] bg-[#101116] custom-scrollbar">
            <AnimatePresence mode="wait">
              {isRunning ? (
                <motion.div
                  key="loading"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="h-full flex flex-col items-center justify-center py-16 space-y-3"
                >
                  <div className="w-48 h-1.5 rounded-full bg-[#222530] overflow-hidden">
                    <motion.div
                      className="h-full bg-[#B8E900] shadow-[0_0_8px_#B8E900]"
                      initial={{ width: '0%' }}
                      animate={{ width: `${simulatedProgress}%` }}
                    />
                  </div>
                  <p className="text-xs font-mono text-[#B8E900]">Đang phân tích và chuyển đổi cấu trúc...</p>
                </motion.div>
              ) : activePreset.rendered.type === 'document' ? (
                <motion.div
                  key="doc"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-4"
                >
                  <div className="border-b border-[#282B37] pb-3">
                    <h4 className="text-base font-bold font-tech uppercase text-white">{activePreset.rendered.title}</h4>
                    <p className="text-xs text-[#B8E900] font-mono mt-0.5">{activePreset.rendered.subtitle}</p>
                  </div>
                  <p className="text-xs text-[#9CA3AF] leading-relaxed">{activePreset.rendered.body}</p>

                  <div className="overflow-x-auto rounded-xl border border-[#282B37] mt-3">
                    <table className="w-full text-[11px] text-left">
                      <thead>
                        <tr className="bg-[#181A22] text-white font-tech uppercase border-b border-[#282B37]">
                          {activePreset.rendered.table?.[0].map((th, i) => (
                            <th key={i} className="p-2 border-r border-[#282B37]">{th}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {activePreset.rendered.table?.slice(1).map((row, rI) => (
                          <tr key={rI} className="border-b border-[#222530] text-[#D1D5DB] font-mono">
                            {row.map((cell, cI) => (
                              <td key={cI} className="p-2 border-r border-[#222530]">{cell}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </motion.div>
              ) : activePreset.rendered.type === 'ocr' ? (
                <motion.div
                  key="ocr"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-3"
                >
                  <div className="flex items-center justify-between p-2 rounded-xl bg-[#181A22] border border-[#282B37] text-xs font-mono">
                    <span className="text-[#9CA3AF]">Độ tin cậy OCR: <strong className="text-[#B8E900]">{activePreset.rendered.confidence}</strong></span>
                    <span className="text-white font-bold">{activePreset.rendered.language}</span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-2">
                    {activePreset.rendered.extracted_fields?.map((field, i) => (
                      <div key={i} className="p-2.5 rounded-xl bg-[#181A22] border border-[#282B37]">
                        <p className="text-[10px] font-mono text-[#6B7280] uppercase">{field.label}</p>
                        <p className="text-xs font-semibold text-white mt-0.5 truncate">{field.value}</p>
                      </div>
                    ))}
                  </div>

                  <div className="p-3 rounded-xl bg-[#181A22] border border-[#282B37] text-xs font-mono text-[#9CA3AF] whitespace-pre-wrap">
                    {activePreset.rendered.rawText}
                  </div>
                </motion.div>
              ) : (
                <motion.pre
                  key="json"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="font-mono text-xs text-[#B8E900] leading-relaxed"
                >
                  {activePreset.rendered.json}
                </motion.pre>
              )}
            </AnimatePresence>
          </div>

          <div className="p-3 bg-[#181A22] border-t border-[#282B37] flex items-center justify-between text-xs font-mono text-[#9CA3AF]">
            <span>Độ trễ trung bình: ~85ms</span>
            <span className="text-[#B8E900] font-bold flex items-center gap-1 font-tech uppercase">
              Khớp cấu trúc 100% <ArrowRight className="w-3 h-3" />
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
