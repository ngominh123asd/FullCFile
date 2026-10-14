import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import {
  UploadCloud,
} from 'lucide-react'
import { filesApi } from '../../lib/api'
import { useTransferStore } from '../../lib/transferStore'
import { useI18n } from '../../lib/i18n'
import toast from 'react-hot-toast'
import { clsx } from 'clsx'

import { SUPPORTED_DROPZONE_ACCEPT } from '../ui/dropzone'

export default function HeroTransformationConsole() {
  const navigate = useNavigate()
  const { t } = useI18n()
  const { setPendingFiles, setUploadedFiles } = useTransferStore()

  const handleDrop = useCallback(
    async (files: File[]) => {
      if (files.length > 0) {
        setPendingFiles(files)
        toast.loading(
          files.length === 1
            ? `Đang nạp "${files[0].name}"...`
            : `Đang nạp ${files.length} tệp tin...`,
          { id: 'hero-drop-upload', duration: 3000 }
        )
        
        try {
          const res = await filesApi.upload(files)
          const uploaded = res.data.files
          setUploadedFiles(uploaded)
          toast.success(
            uploaded.length === 1
              ? `Đã sẵn sàng chuyển đổi: ${uploaded[0].original_filename}`
              : `Đã sẵn sàng chuyển đổi: ${uploaded.length} tệp tin`,
            { id: 'hero-drop-upload' }
          )
          navigate('/dashboard')
        } catch (err: any) {
          const errorMsg = err.response?.data?.detail || err.message || 'Tải tệp tin thất bại'
          toast.error(errorMsg, { id: 'hero-drop-upload', duration: 4500 })
        }
      }
    },
    [navigate, setPendingFiles, setUploadedFiles]
  )

  const handleDropRejected = useCallback((fileRejections: any[]) => {
    if (fileRejections.length > 0) {
      const first = fileRejections[0]
      const code = first.errors?.[0]?.code
      if (code === 'file-invalid-type') {
        toast.error(
          `Định dạng tệp "${first.file.name}" không được hỗ trợ. Vui lòng chọn tệp: PDF, DOCX, DOC, XLSX, XLS, CSV, PPTX, Ảnh, Markdown...`
        )
      } else {
        toast.error(`Tệp "${first.file.name}" không hợp lệ.`)
      }
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    onDropRejected: handleDropRejected,
    accept: SUPPORTED_DROPZONE_ACCEPT,
    maxFiles: 10,
    noClick: false
  })

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      {/* ZZZ Hardware Device Frame (Screenshot 1: .FUNCTIONS Device) */}
      <div className="zzz-device-frame overflow-hidden">
        {/* Device Top Machine Bar */}
        <div className="px-5 py-3 bg-[#14151C] border-b border-[#282B37] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-[#B8E900]" />
            <span className="text-xs font-tech font-bold uppercase tracking-wider text-white">
              .FUNCTIONS // INTER-KNOT CONSOLE
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-white bg-[#222530] px-2.5 py-0.5 rounded-full border border-[#2E313E] font-bold">
              AST READY
            </span>
          </div>
        </div>

        {/* Dropzone Area with Tactile Dark Surface */}
        <div className="p-6 sm:p-8 bg-[#181A22]">
          <div
            {...getRootProps()}
            className={clsx(
              "relative group rounded-2xl border-2 border-dashed transition-all duration-200 cursor-pointer overflow-hidden p-8 sm:p-12 text-center select-none",
              isDragActive
                ? "border-[#B8E900] bg-[#222530]"
                : "border-[#323646] bg-[#14151C] hover:border-[#B8E900]/70 hover:bg-[#1E202A]"
            )}
          >
            <input {...getInputProps()} />

            <div className="flex flex-col items-center justify-center space-y-4 relative z-10">
              {/* Tactile Device Button Tile */}
              <div className="w-16 h-16 rounded-2xl bg-[#242733] border border-[#353846] group-hover:border-[#B8E900] flex items-center justify-center shadow-lg transition-all">
                <UploadCloud className="w-8 h-8 text-white group-hover:text-[#B8E900] group-hover:scale-110 transition-transform" />
              </div>

              {/* Main Callout */}
              <div className="space-y-1">
                <p className="text-base sm:text-lg font-tech font-bold uppercase tracking-wider text-white group-hover:text-[#B8E900] transition-colors">
                  {t('hero.drag_or_click')}
                </p>
                <p className="text-xs font-mono text-[#9CA3AF] max-w-md mx-auto">
                  [ THẢ TÀI LIỆU VÀO ĐỂ TỰ ĐỘNG NHẬN DIỆN VÀ CHUYỂN ĐỔI TỨC THÌ ]
                </p>
              </div>

              {/* Supported Format Grid Tiles (Screenshot 1: Tiles) */}
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 pt-2 max-w-lg w-full">
                {[
                  'DOCX',
                  'PDF',
                  'MARKDOWN',
                  'HTML',
                  'OCR ẢNH',
                  'EXCEL'
                ].map((name) => (
                  <div
                    key={name}
                    className="p-2 rounded-xl bg-[#222530] border border-[#2E313E] text-center"
                  >
                    <span className="text-[11px] font-mono font-bold text-white block">
                      {name}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Console Device Footer Strip */}
        <div className="px-5 py-2.5 bg-[#14151C] border-t border-[#282B37] flex flex-wrap items-center justify-between text-[11px] font-mono text-[#6B7280] gap-2">
          <span className="flex items-center gap-1.5 text-white font-bold">
            <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />
            CONVERTER ENGINE ARMED
          </span>
          <span className="text-[#9CA3AF]">
            PADDLE OCR • PANDOC AST • LIBREOFFICE 7.6
          </span>
        </div>
      </div>
    </div>
  )
}
