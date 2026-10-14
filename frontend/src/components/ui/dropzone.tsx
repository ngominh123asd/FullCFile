import { useCallback, useState } from 'react'
import { useDropzone, FileRejection } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { UploadCloud, FileText, Image as ImageIcon, Table as TableIcon, X, Check, ArrowUpRight } from 'lucide-react'
import toast from 'react-hot-toast'
import { formatBytes } from '../../lib/utils'
import { useI18n } from '../../lib/i18n'

export const SUPPORTED_DROPZONE_ACCEPT: Record<string, string[]> = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'application/vnd.ms-excel': ['.xls'],
  'text/csv': ['.csv'],
  'application/vnd.oasis.opendocument.spreadsheet': ['.ods'],
  'application/json': ['.json'],
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'text/html': ['.html', '.htm'],
  'application/rtf': ['.rtf'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/webp': ['.webp'],
  'image/bmp': ['.bmp'],
  'image/tiff': ['.tiff', '.tif'],
  'image/gif': ['.gif'],
}

interface DropZoneProps {
  onFilesSelected: (files: File[]) => void
  isLoading?: boolean
  maxFiles?: number
  maxSize?: number
  acceptTypes?: string[]
  showQueue?: boolean
  compact?: boolean
  helperText?: string
}

export default function DropZone({
  onFilesSelected,
  isLoading = false,
  maxFiles = 10,
  maxSize = 100 * 1024 * 1024,
  showQueue = false,
  compact = false,
  helperText,
}: DropZoneProps) {
  const { t } = useI18n()
  const [queuedFiles, setQueuedFiles] = useState<File[]>([])

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) {
        setQueuedFiles(accepted)
        onFilesSelected(accepted)
      }
    },
    [onFilesSelected]
  )

  const onDropRejected = useCallback(
    (fileRejections: FileRejection[]) => {
      if (fileRejections.length > 0) {
        const first = fileRejections[0]
        const code = first.errors?.[0]?.code
        if (code === 'file-invalid-type') {
          toast.error(
            `Định dạng tệp "${first.file.name}" không được hỗ trợ. Vui lòng chọn tệp: PDF, DOCX, DOC, XLSX, XLS, CSV, PPTX, Ảnh, Markdown...`
          )
        } else if (code === 'file-too-large') {
          toast.error(`Tệp "${first.file.name}" vượt quá dung lượng tối đa (${formatBytes(maxSize)}).`)
        } else if (code === 'too-many-files') {
          toast.error(`Vượt quá số lượng tệp cho phép (tối đa ${maxFiles} tệp).`)
        } else {
          toast.error(`Tệp "${first.file.name}" không hợp lệ.`)
        }
      }
    },
    [maxSize, maxFiles]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
    accept: SUPPORTED_DROPZONE_ACCEPT,
    maxFiles,
    maxSize,
    disabled: isLoading,
  })

  const removeFile = (e: React.MouseEvent, index: number) => {
    e.stopPropagation()
    const updated = queuedFiles.filter((_, i) => i !== index)
    setQueuedFiles(updated)
    if (updated.length > 0) {
      onFilesSelected(updated)
    }
  }

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase() || ''
    if (['png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'].includes(ext)) {
      return <ImageIcon className="w-5 h-5 text-white" />
    }
    if (['xlsx', 'csv', 'ods', 'json'].includes(ext)) {
      return <TableIcon className="w-5 h-5 text-white" />
    }
    return <FileText className="w-5 h-5 text-white" />
  }

  return (
    <div className="w-full">
      {/* Outer ZZZ Device Frame (Screenshot 1) */}
      <div className="zzz-device-frame overflow-hidden">
        {/* Device Top Machine Bar */}
        <div className="px-5 py-3 bg-[#14151C] border-b border-[#282B37] flex items-center justify-between flex-wrap gap-2 text-xs font-mono select-none">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#B8E900]" />
            <span className="font-tech font-bold text-white uppercase tracking-wider text-xs">
              KHAY TIẾP NHẬN BĂNG TÀI LIỆU
            </span>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-[#9CA3AF]">
            <span className="px-2 py-0.5 rounded-full bg-[#222530] border border-[#2F3240] text-white font-bold">
              AST ENGINE READY
            </span>
          </div>
        </div>

        {/* Interactive Drop Zone Area */}
        <div
          {...getRootProps()}
          className={`relative group cursor-pointer transition-all duration-200 ${
            compact ? 'p-4' : 'p-6 sm:p-8 md:p-10'
          } ${
            isDragActive
              ? 'bg-[#1C1E28] border-2 border-[#B8E900]'
              : 'bg-[#181A22] hover:bg-[#1E202A] border-2 border-dashed border-[#303342] hover:border-[#B8E900]/70'
          } ${isLoading ? 'pointer-events-none opacity-60' : ''}`}
        >
          <input {...getInputProps()} />

          {compact ? (
            <div className="flex items-center justify-between gap-4 relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#242733] border border-[#353846] flex items-center justify-center text-white flex-shrink-0">
                  <UploadCloud className="w-5 h-5" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-tech font-bold text-white group-hover:text-[#B8E900] transition-colors">
                    NẠP TÀI LIỆU MỚI
                  </p>
                  <p className="text-xs font-mono text-[#9CA3AF]">
                    {helperText || 'Tự động nhận diện định dạng nguồn'}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-xs font-tech font-bold text-[#0C0D10] bg-[#B8E900] px-3.5 py-1.5 rounded-full flex-shrink-0">
                <span>CHỌN TỆP</span>
                <ArrowUpRight className="w-3.5 h-3.5 stroke-[3]" />
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center space-y-4 relative z-10 text-center">
              {/* Central Tactile Icon Container */}
              <div className="w-16 h-16 rounded-2xl bg-[#242733] border border-[#353846] group-hover:border-[#B8E900] flex items-center justify-center shadow-lg transition-all">
                <UploadCloud className="w-8 h-8 text-white group-hover:text-[#B8E900] group-hover:scale-110 transition-transform" />
              </div>

              {/* Title & Instructions */}
              <div className="space-y-1">
                <p className="text-base sm:text-lg font-tech font-bold uppercase tracking-wider text-white group-hover:text-[#B8E900] transition-colors">
                  {t('studio.drop_title')}
                </p>
                <p className="text-xs sm:text-sm font-mono text-[#9CA3AF]">
                  {helperText || t('studio.drop_sub')}
                </p>
              </div>

              {/* Supported Format Grid Tiles (Screenshot 1: .FUNCTIONS style tiles) */}
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 pt-2 max-w-xl w-full">
                {[
                  { name: 'DOCX', sub: 'Word' },
                  { name: 'PDF', sub: 'Vector' },
                  { name: 'MARKDOWN', sub: 'GFM' },
                  { name: 'HTML', sub: 'Web' },
                  { name: 'OCR', sub: 'Ảnh' },
                  { name: 'EXCEL', sub: 'Bảng tính' },
                ].map((item) => (
                  <div
                    key={item.name}
                    className="p-2 rounded-xl bg-[#222530] border border-[#2E313E] group-hover:border-[#3D4254] text-center transition-all"
                  >
                    <span className="text-[11px] font-mono font-bold text-white block">
                      {item.name}
                    </span>
                    <span className="text-[9px] font-mono text-[#6B7280]">
                      {item.sub}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Staged Files Queue Styled as Tactile Tiles */}
      <AnimatePresence>
        {showQueue && queuedFiles.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mt-4 space-y-2.5"
          >
            <div className="flex items-center justify-between text-xs font-mono text-[#9CA3AF] px-1 pb-1 border-b border-[#262834]">
              <span className="font-tech font-bold uppercase text-white flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900]" />
                HÀNG ĐỢI ĐÃ NẠP: {queuedFiles.length} TẬP TIN
              </span>
              <span className="text-white flex items-center gap-1 font-bold">
                <Check className="w-3.5 h-3.5 text-[#B8E900]" /> SẴN SÀNG
              </span>
            </div>

            {queuedFiles.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 rounded-xl bg-[#1C1E26] border border-[#2D303E] hover:border-[#4A5064] transition-colors group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-[#242733] border border-[#323646]">
                    {getFileIcon(file.name)}
                  </div>
                  <div className="truncate text-left">
                    <p className="text-sm font-tech font-bold text-white truncate">
                      {file.name}
                    </p>
                    <p className="text-xs font-mono text-[#9CA3AF]">
                      <span className="text-white font-bold">[{file.name.split('.').pop()?.toUpperCase()}]</span> • {formatBytes(file.size)} • VỊ TRÍ #{idx + 1}
                    </p>
                  </div>
                </div>

                {/* Eject Button */}
                <button
                  type="button"
                  onClick={(e) => removeFile(e, idx)}
                  title="Nhả băng"
                  className="p-1.5 rounded-lg bg-[#242733] border border-[#323646] text-[#FF3355] hover:bg-[#FF3355] hover:text-white transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
