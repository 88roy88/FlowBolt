### lucide-react — icons
Use lucide-react icons to clarify nav, status, actions, and metrics:
```tsx
import { Search, Plus, Trash2 } from 'lucide-react';
<button aria-label="Delete"><Trash2 className="w-4 h-4 text-gray-500" /></button>
```
Why: import each icon by its exact PascalCase name (e.g. Trash2).
Why: icons inherit currentColor, so Tailwind text-color classes tint them; size with w-*/h-* or the size prop.
Pair each icon with a text label or aria-label — the icon should not be the only label.
