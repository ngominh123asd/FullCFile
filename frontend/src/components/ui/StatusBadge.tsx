import React from 'react'
import { JobStatus } from '../../types'
import { Check, Settings, Clock, AlertTriangle } from 'lucide-react'
import { cn } from '../../lib/utils'

interface StatusBadgeProps {
  status: JobStatus | string
  className?: string
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  switch (status) {
    case 'completed':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#B8E900] text-[#0C0D10] text-xs font-tech font-black uppercase tracking-wider shadow-[0_2px_8px_rgba(184,233,0,0.3)]',
            className
          )}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#0C0D10]" />
          <Check className="w-3.5 h-3.5 text-[#0C0D10] stroke-[3]" />
          <span>[ HOÀN THÀNH ]</span>
        </span>
      )
    case 'processing':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#222530] text-white border border-[#3A3E4E] text-xs font-tech font-bold uppercase tracking-wider',
            className
          )}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#B8E900] animate-pulse" />
          <Settings className="w-3.5 h-3.5 text-white animate-spin" />
          <span>[ ĐANG XỬ LÝ... ]</span>
        </span>
      )
    case 'failed':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#221418] text-[#FF3355] border border-[#FF3355]/40 text-xs font-tech font-bold uppercase tracking-wider',
            className
          )}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#FF3355] animate-pulse" />
          <AlertTriangle className="w-3.5 h-3.5 text-[#FF3355]" />
          <span>[ THẤT BẠI ]</span>
        </span>
      )
    case 'pending':
    default:
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#1C1E26] text-[#9CA3AF] border border-[#2E313E] text-xs font-tech font-bold uppercase tracking-wider',
            className
          )}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#9CA3AF]" />
          <Clock className="w-3.5 h-3.5 text-[#9CA3AF]" />
          <span>[ HÀNG ĐỢI ]</span>
        </span>
      )
  }
}
