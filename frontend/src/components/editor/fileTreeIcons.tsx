import { File, FileCode, FileJson, FileText as FileTextIcon, Image, Settings } from 'lucide-react';

export function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'json': return <FileJson size={14} className="shrink-0 text-[#c9a04a]" />;
    case 'ts': case 'tsx': return <FileCode size={14} className="shrink-0 text-[#5a9bcf]" />;
    case 'js': case 'jsx': return <FileCode size={14} className="shrink-0 text-[#c4b456]" />;
    case 'css': case 'scss': return <FileCode size={14} className="shrink-0 text-[#6b8fd4]" />;
    case 'html': return <FileCode size={14} className="shrink-0 text-[#c47a5a]" />;
    case 'md': return <FileTextIcon size={14} className="shrink-0 text-muted-foreground" />;
    case 'png': case 'jpg': case 'svg': case 'gif': return <Image size={14} className="shrink-0 text-[#7ab88a]" />;
    case 'toml': case 'yaml': case 'yml': return <Settings size={14} className="shrink-0 text-muted-foreground" />;
    default: return <File size={14} className="shrink-0 text-muted-foreground" />;
  }
}
