import { useState } from 'react'
import { Search, ChevronLeft, ChevronRight, Download } from 'lucide-react'
import { Button } from './button'

interface SheetData {
  name: string
  data: (string | number | null)[][]
}

interface InteractiveGridProps {
  sheets?: SheetData[]
  csvData?: (string | number | null)[][]
  title?: string
}

export default function InteractiveGrid({ sheets, csvData }: InteractiveGridProps) {
  const allSheets: SheetData[] = sheets && sheets.length > 0 
    ? sheets 
    : [{ name: 'Sheet 1', data: csvData || [] }]

  const [activeSheetIndex, setActiveSheetIndex] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 15

  const currentSheet = allSheets[activeSheetIndex] || { name: 'Sheet 1', data: [] }
  const rawRows = currentSheet.data || []
  const headers = rawRows.length > 0 ? rawRows[0] : []
  const bodyRows = rawRows.length > 1 ? rawRows.slice(1) : []

  // Filter rows based on search
  const filteredRows = bodyRows.filter((row) =>
    row.some((cell) => String(cell || '').toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize))
  const displayedRows = filteredRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  const exportCurrentCSV = () => {
    const csvContent = rawRows.map((r) => r.map((c) => `"${String(c || '').replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentSheet.name}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="w-full rounded-2xl bg-[#181A22] border-2 border-[#2C2F3D] overflow-hidden shadow-xl">
      {/* Top Header & Search */}
      <div className="p-3.5 sm:p-4 bg-[#14151C] border-b border-[#282B37] flex flex-wrap items-center justify-between gap-3">
        {/* Sheet Tabs */}
        {allSheets.length > 1 && (
          <div className="flex items-center gap-1 bg-[#181A22] p-1 rounded-full border border-[#282B37] overflow-x-auto custom-scrollbar">
            {allSheets.map((s, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setActiveSheetIndex(idx)
                  setCurrentPage(1)
                }}
                className={`px-3 py-1 rounded-full text-xs font-tech font-bold uppercase whitespace-nowrap transition-all ${
                  activeSheetIndex === idx
                    ? 'bg-[#B8E900] text-[#0C0D10] shadow-[0_2px_8px_rgba(184,233,0,0.3)]'
                    : 'text-[#9CA3AF] hover:text-white hover:bg-white/5'
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>
        )}

        <div className="flex items-center gap-3 ml-auto">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value)
                setCurrentPage(1)
              }}
              placeholder="Tìm kiếm trong bảng..."
              className="h-8 pl-8 pr-3 text-xs rounded-xl bg-[#222530] border border-[#2E313E] text-white placeholder-[#6B7280] focus:outline-none focus:border-[#B8E900]"
            />
          </div>

          <Button variant="secondary" size="sm" onClick={exportCurrentCSV} className="text-xs h-8">
            <Download className="w-3.5 h-3.5 text-[#B8E900]" />
            <span>XUẤT CSV</span>
          </Button>
        </div>
      </div>

      {/* Spreadsheet Table View */}
      <div className="overflow-x-auto max-h-[480px] custom-scrollbar">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-[#181A22] border-b border-[#282B37] text-[#9CA3AF] font-mono sticky top-0 z-10">
              <th className="p-2.5 w-12 text-center text-[#6B7280] border-r border-[#282B37]">#</th>
              {headers.map((h, i) => (
                <th key={i} className="p-2.5 font-bold font-tech text-white border-r border-[#282B37] whitespace-nowrap">
                  {String(h || `CỘT ${i + 1}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {displayedRows.length > 0 ? (
              displayedRows.map((row, rIdx) => {
                const globalRowNumber = (currentPage - 1) * pageSize + rIdx + 1
                return (
                  <tr
                    key={rIdx}
                    className="border-b border-[#222530] hover:bg-[#222530]/60 transition-colors font-mono"
                  >
                    <td className="p-2.5 text-center text-[#6B7280] bg-[#14151C] border-r border-[#282B37] select-none">
                      {globalRowNumber}
                    </td>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="p-2.5 text-[#F8FAFC] border-r border-[#222530] truncate max-w-[240px]">
                        {cell !== null && cell !== undefined ? String(cell) : ''}
                      </td>
                    ))}
                  </tr>
                )
              })
            ) : (
              <tr>
                <td colSpan={headers.length + 1} className="py-12 text-center text-[#6B7280] font-mono">
                  Không tìm thấy kết quả phù hợp
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination & Count */}
      <div className="p-3 bg-[#14151C] border-t border-[#282B37] flex items-center justify-between text-xs font-mono text-[#9CA3AF]">
        <span>
          Hiển thị {filteredRows.length > 0 ? (currentPage - 1) * pageSize + 1 : 0}-
          {Math.min(currentPage * pageSize, filteredRows.length)} / {filteredRows.length} dòng
        </span>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
            className="h-7 w-7"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="font-bold text-white">
            {currentPage} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
            className="h-7 w-7"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}
