import { Search, Wrench, Save, TestTube, RefreshCw, FolderSearch, FileText, Pencil } from 'lucide-react';
import type { FixStep, FollowUpStep } from '../../../types';

export function getStepIcon(step: FixStep['step']) {
  switch (step) {
    case 'discover':
      return Search;
    case 'generate':
      return Wrench;
    case 'write':
      return Save;
    case 'validate':
      return TestTube;
    case 'retry':
      return RefreshCw;
  }
}

export function getFollowUpToolIcon(tool: FollowUpStep['tool']) {
  switch (tool) {
    case 'grep':
      return Search;
    case 'glob':
      return FolderSearch;
    case 'read_file':
      return FileText;
    case 'write_file':
      return Save;
    case 'edit_file':
      return Pencil;
  }
}

export function getFollowUpToolLabel(tool: FollowUpStep['tool'], args: Record<string, string>, isRunning?: boolean) {
  switch (tool) {
    case 'grep':
      return isRunning
        ? `Searching for '${args.pattern || ''}'${args.path && args.path !== '/' ? ` in ${args.path}` : ''}`
        : `Searched for '${args.pattern || ''}'${args.path && args.path !== '/' ? ` in ${args.path}` : ''}`;
    case 'glob':
      return isRunning ? `Finding files: ${args.pattern || ''}` : `Found files: ${args.pattern || ''}`;
    case 'read_file':
      return isRunning ? `Reading ${args.path || ''}` : `Read ${args.path || ''}`;
    case 'write_file':
      return isRunning ? `Writing ${args.path || ''}` : `Wrote ${args.path || ''}`;
    case 'edit_file':
      return isRunning ? `Editing ${args.path || ''}` : `Edited ${args.path || ''}`;
  }
}
