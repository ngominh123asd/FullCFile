export default function ArchitecturalBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden select-none z-0">
      {/* 1. Deep Carbon Black Base with In-Game Diagonal Texture */}
      <div className="absolute inset-0 zzz-carbon-bg" />

      {/* 2. ZZZ In-Game Comic Filmstrip & Graphic Motif Watermark (Screenshot 2 & 3) */}
      <div className="absolute inset-0 opacity-10 pointer-events-none overflow-hidden">
        {/* Slanted Filmstrip Lines */}
        <div 
          className="absolute -top-20 -left-20 w-[140%] h-[140%] pointer-events-none"
          style={{
            transform: 'rotate(-12deg)',
            backgroundImage: `
              linear-gradient(to right, rgba(255, 255, 255, 0.08) 2px, transparent 2px),
              linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
            `,
            backgroundSize: '120px 60px',
          }}
        />
        {/* Subtle Watermark Logo Text */}
        <div className="absolute right-10 top-1/3 text-[140px] font-black font-tech text-white/[0.02] tracking-tighter select-none rotate-90">
          ZENLESS
        </div>
      </div>
    </div>
  )
}
