import { motion } from 'framer-motion'

interface LoadingScreenProps {
  message?: string
}

export default function LoadingScreen({ message = 'Đang tải hệ thống...' }: LoadingScreenProps) {
  return (
    <div className="min-h-screen zzz-carbon-bg flex items-center justify-center p-4">
      <div className="zzz-device-frame p-8 max-w-sm w-full flex flex-col items-center gap-6 text-center shadow-2xl">
        {/* Animated ZZZ Charm Badge */}
        <motion.div
          animate={{
            scale: [1, 1.05, 1],
            rotate: [0, 5, -5, 0],
          }}
          transition={{
            duration: 2.5,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
          className="w-16 h-16 rounded-2xl bg-[#242733] border-2 border-[#353846] text-[#B8E900] flex items-center justify-center font-tech font-black text-3xl shadow-[0_4px_16px_rgba(0,0,0,0.6)]"
        >
          Z
        </motion.div>

        {/* Loading Text */}
        <div className="flex flex-col items-center gap-2">
          <p className="text-white font-tech font-bold uppercase tracking-wider text-sm">{message}</p>
          <div className="flex gap-1.5">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.1, 0.8] }}
                transition={{
                  duration: 1.2,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
                className="w-2 h-2 rounded-full bg-[#B8E900]"
              />
            ))}
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full bg-[#222530] overflow-hidden border border-[#2E313E]">
          <motion.div
            animate={{ x: ['-100%', '100%'] }}
            transition={{
              duration: 1.4,
              repeat: Infinity,
              ease: 'linear',
            }}
            className="h-full w-1/2 bg-[#B8E900] shadow-[0_0_8px_rgba(184,233,0,0.8)]"
          />
        </div>

        <span className="text-[10px] font-mono text-[#6B7280] uppercase tracking-wider">
          FILEFORGE // HARDWARE PROXY ENGINE
        </span>
      </div>
    </div>
  )
}
