import { useState, useRef, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

interface PageSizeDropdownProps {
  value: number
  onChange: (value: number) => void
  options?: number[]
  label?: string
}

export default function PageSizeDropdown({
  value,
  onChange,
  options = [5, 10, 20, 50],
  label = 'Hiển thị:'
}: PageSizeDropdownProps) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div className="relative inline-flex items-center text-xs font-mono select-none flex-shrink-0" ref={dropdownRef}>
      {label && <span className="text-[#9CA3AF] mr-2 hidden sm:inline text-[11px] font-mono">{label}</span>}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 h-8 px-2.5 bg-[#222530] hover:bg-[#2B2E3C] text-white font-tech font-bold rounded-xl border border-[#323646] hover:border-[#B8E900] transition-all shadow-[0_2px_8px_rgba(0,0,0,0.5)] active:scale-95 cursor-pointer"
        aria-expanded={isOpen}
      >
        <span className="min-w-[14px] text-center font-mono">{value}</span>
        <ChevronDown
          className={`w-3.5 h-3.5 text-[#9CA3AF] transition-transform duration-200 ${
            isOpen ? 'rotate-180 text-[#B8E900]' : ''
          }`}
        />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.95 }}
            transition={{ duration: 0.12, ease: 'easeOut' }}
            className="absolute right-0 top-full mt-1.5 w-16 bg-[#181A22] border border-[#323646] rounded-xl shadow-[0_8px_24px_rgba(0,0,0,0.8)] p-1 z-[100] flex flex-col gap-0.5"
          >
            {options.map((opt) => {
              const isSelected = value === opt
              return (
                <button
                  key={opt}
                  type="button"
                  onClick={() => {
                    onChange(opt)
                    setIsOpen(false)
                  }}
                  className={`w-full text-center py-1 rounded-lg text-xs font-mono transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-[#B8E900] text-[#0C0D10] font-black shadow-[0_2px_6px_rgba(184,233,0,0.3)]'
                      : 'text-[#9CA3AF] hover:text-white hover:bg-[#222530] font-semibold'
                  }`}
                >
                  {opt}
                </button>
              )
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
