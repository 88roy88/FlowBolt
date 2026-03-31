import type { editor } from 'monaco-editor';

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
