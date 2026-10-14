import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'
import { Loader2 } from 'lucide-react'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap text-xs sm:text-sm font-tech font-bold uppercase tracking-wider transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#B8E900] disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer',
  {
    variants: {
      variant: {
        primary:
          'bg-[#B8E900] text-[#0C0D10] font-black rounded-xl border border-[#B8E900] shadow-[0_4px_14px_rgba(184,233,0,0.3)] hover:bg-[#C6F202] hover:shadow-[0_6px_20px_rgba(184,233,0,0.45)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_2px_8px_rgba(184,233,0,0.3)]',
        secondary:
          'bg-[#222530] text-white rounded-xl border border-[#323646] hover:bg-[#2B2E3C] hover:border-[#4A5066] hover:text-white shadow-[0_4px_10px_rgba(0,0,0,0.4)] hover:-translate-y-0.5 active:translate-y-0',
        white:
          'bg-white text-[#0C0D10] font-black rounded-xl border border-white hover:bg-[#E5E7EB] shadow-[0_4px_12px_rgba(0,0,0,0.4)] hover:-translate-y-0.5 active:translate-y-0',
        outline:
          'bg-[#181A22] text-[#D1D5DB] rounded-xl border border-[#323646] hover:bg-[#222530] hover:border-[#B8E900] hover:text-[#B8E900] shadow-sm',
        ghost:
          'text-[#9CA3AF] hover:text-white hover:bg-[#222530] rounded-xl font-medium',
        danger:
          'bg-[#2A1518] text-[#FF4D6D] border border-[#FF4D6D]/40 hover:bg-[#381B20] hover:border-[#FF4D6D] rounded-xl shadow-sm',
        plate:
          'bg-[#181A22] text-white border border-[#2D303E] hover:border-[#4A5064] hover:bg-[#222530] rounded-xl shadow-sm',
        // Backward-compatibility aliases for legacy arcade styles
        'arcade-cyan':
          'bg-[#B8E900] text-[#0C0D10] font-black rounded-xl border border-[#B8E900] shadow-[0_4px_14px_rgba(184,233,0,0.3)] hover:bg-[#C6F202]',
        'arcade-amber':
          'bg-[#FF5E00] text-white font-black rounded-xl border border-[#FF5E00] shadow-[0_4px_14px_rgba(255,94,0,0.3)] hover:bg-[#FF7724]',
        'arcade-pink':
          'bg-[#FF3355] text-white font-black rounded-xl border border-[#FF3355] shadow-[0_4px_14px_rgba(255,51,85,0.3)] hover:bg-[#FF4D6D]',
      },
      size: {
        sm: 'h-8 px-3 text-xs',
        default: 'h-10 px-4 py-2',
        lg: 'h-12 px-6 text-sm sm:text-base font-bold',
        xl: 'h-14 px-8 text-base font-black',
        icon: 'h-9 w-9 p-0 rounded-xl',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  isLoading?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, isLoading = false, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && <Loader2 className="w-4 h-4 animate-spin text-current" />}
        {children}
      </Comp>
    )
  }
)
Button.displayName = 'Button'
