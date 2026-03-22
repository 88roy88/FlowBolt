export default function App() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
      <div className="text-center space-y-6">
        <div className="relative">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
          </div>
          <div className="absolute inset-0 w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 blur-xl opacity-30 animate-pulse" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold text-white tracking-tight">
            Ready to build
          </h1>
          <p className="text-slate-400 text-sm max-w-xs mx-auto">
            Describe what you'd like to create and Flow44 will generate it for you
          </p>
        </div>
        <div className="flex items-center justify-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:0ms]" />
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:150ms]" />
          <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:300ms]" />
        </div>
        <div className="flex items-center justify-center pt-4">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="#2bbcc4">
            <path d="M6.5 3.8C5.3 3.05 3.75 3.92 3.75 5.33v13.34c0 1.41 1.55 2.28 2.75 1.53l11.25-6.67c1.15-.72 1.15-2.34 0-3.06L6.5 3.8z" />
          </svg>
          <span className="text-3xl font-bold tracking-tight">
            <span className="text-[#2bbcc4]">FLOW</span>
            <span className="text-white">44</span>
          </span>
        </div>
      </div>
    </div>
  )
}
