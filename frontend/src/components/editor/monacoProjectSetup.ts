import type { Monaco } from '@monaco-editor/react';
import type { editor, IPosition } from 'monaco-editor';
import {
  findImportedModuleForSymbol,
  normalizeProjectPath,
  resolveRelativeImportPath,
  toMonacoUri,
} from './editorFilePaths';
import {
  getMonacoReactViteAmbientSource,
  MONACO_REACT_VITE_DTS_URI,
  MONACO_REACT_VITE_JS_DTS_URI,
} from './monacoAmbientTypes';

let monacoTypeLibDisposables: Array<{ dispose(): void }> = [];
let definitionProviderDisposable: { dispose(): void } | null = null;

export function installMonacoProjectTypes(
  monaco: Monaco,
  getIndexedFilePaths: () => Set<string>,
  openFile: (path: string, line?: number, col?: number) => Promise<void>,
): void {
  try {
    const tsDefaults = monaco.languages.typescript.typescriptDefaults;
    const jsDefaults = monaco.languages.typescript.javascriptDefaults;

    const sharedCompilerOptions: Parameters<typeof tsDefaults.setCompilerOptions>[0] = {
      target: monaco.languages.typescript.ScriptTarget.ES2020,
      module: monaco.languages.typescript.ModuleKind.ESNext,
      moduleResolution: monaco.languages.typescript.ModuleResolutionKind.NodeJs,
      jsx: monaco.languages.typescript.JsxEmit.ReactJSX,
      allowJs: true,
      allowNonTsExtensions: true,
      allowImportingTsExtensions: true,
      esModuleInterop: true,
      isolatedModules: true,
      resolveJsonModule: true,
      useDefineForClassFields: true,
      strict: true,
      skipLibCheck: true,
      noEmit: true,
    };

    tsDefaults.setCompilerOptions(sharedCompilerOptions);
    jsDefaults.setCompilerOptions(sharedCompilerOptions);

    tsDefaults.setDiagnosticsOptions({ noSemanticValidation: false, noSyntaxValidation: false });
    jsDefaults.setDiagnosticsOptions({ noSemanticValidation: false, noSyntaxValidation: false });
    tsDefaults.setEagerModelSync(true);
    jsDefaults.setEagerModelSync(true);

    const reactTypes = getMonacoReactViteAmbientSource();

    for (const disposable of monacoTypeLibDisposables) {
      disposable.dispose();
    }
    monacoTypeLibDisposables = [
      tsDefaults.addExtraLib(reactTypes, MONACO_REACT_VITE_DTS_URI),
      jsDefaults.addExtraLib(reactTypes, MONACO_REACT_VITE_JS_DTS_URI),
    ];

    const makeProvider = () => ({
      async provideDefinition(model: editor.ITextModel, position: IPosition) {
        const word = model.getWordAtPosition(position);
        if (!word?.word) return null;

        const importPath = findImportedModuleForSymbol(model.getValue(), word.word);
        if (!importPath) return null;

        const currentPath = normalizeProjectPath(decodeURIComponent(model.uri.path));
        const targetPath = resolveRelativeImportPath(currentPath, importPath, getIndexedFilePaths());
        if (!targetPath) return null;

        await openFile(targetPath);
        return {
          uri: monaco.Uri.parse(toMonacoUri(targetPath)),
          range: new monaco.Range(1, 1, 1, 1),
        };
      },
    });

    definitionProviderDisposable?.dispose();
    definitionProviderDisposable = monaco.languages.registerDefinitionProvider(
      ['typescript', 'javascript'],
      makeProvider(),
    );
  } catch (err) {
    console.error('Monaco types init failed, will retry on next mount:', err);
    for (const disposable of monacoTypeLibDisposables) {
      disposable.dispose();
    }
    monacoTypeLibDisposables = [];
    definitionProviderDisposable?.dispose();
    definitionProviderDisposable = null;
  }
}
