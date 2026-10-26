const SKELETON_BUBBLES = [
  { isUser: true, lines: ['w-full', 'w-2/3'] },
  { isUser: false, lines: ['w-full', 'w-11/12', 'w-full', 'w-4/5', 'w-full', 'w-3/4', 'w-1/2'] },
  { isUser: true, lines: ['w-full'] },
  { isUser: false, lines: ['w-full', 'w-full', 'w-5/6', 'w-full', 'w-2/3'] },
  { isUser: true, lines: ['w-full', 'w-3/4', 'w-1/3'] },
  { isUser: false, lines: ['w-full', 'w-11/12', 'w-full', 'w-full', 'w-4/5', 'w-full', 'w-full', 'w-3/5'] },
];

export function ChatSkeleton() {
  return (
    <div className="flex flex-col gap-4 animate-pulse" aria-hidden>
      {SKELETON_BUBBLES.map(({ isUser, lines }, i) => (
        <div key={i} className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
          <div
            className={`flex flex-col gap-2.5 px-3.5 py-3.5 rounded-xl ${
              isUser ? 'w-[45%] items-end bg-user-bubble/60 border border-primary/15' : 'w-[85%] bg-assistant-bubble/60 border border-border/60'
            }`}
          >
            {lines.map((w, j) => (
              <div key={j} className={`h-3 rounded-full bg-muted-foreground/15 ${w}`} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
