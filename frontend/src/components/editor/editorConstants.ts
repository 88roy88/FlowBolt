import type { editor } from 'monaco-editor';

export const FILE_TREE_MIN = 120;
export const FILE_TREE_MAX = 400;

export const EDITOR_MONACO_OPTIONS: editor.IStandaloneEditorConstructionOptions = {
  minimap: { enabled: false },
  fontSize: 13,
  lineNumbers: 'on',
  scrollBeyondLastLine: false,
  wordWrap: 'on',
  tabSize: 2,
  automaticLayout: true,
  definitionLinkOpensInPeek: false,
  gotoLocation: {
    multipleDefinitions: 'goto',
    multipleDeclarations: 'goto',
    multipleImplementations: 'goto',
    multipleReferences: 'peek',
    multipleTypeDefinitions: 'goto',
  },
};

export const INITIAL_VISIBLE_RESULTS = 50;

export const CODE_EXTS = new Set(['ts', 'tsx', 'js', 'jsx', 'py', 'java', 'cpp', 'c', 'go', 'rs']);

export const SEARCH_OPTION_LABEL_STYLE: React.CSSProperties = {
  display: 'flex', gap: 4, alignItems: 'center', fontSize: 11,
  color: 'var(--muted-foreground)', cursor: 'pointer',
  padding: '2px 6px', borderRadius: 3, transition: 'background 0.2s',
};
