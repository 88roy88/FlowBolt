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
let monacoImportDefinitionProviderInitialized = false;

/**
 * Configures TS/JS defaults, injects ambient libs, and registers the import definition provider once.
 * Call from Monaco `beforeMount` with a getter so indexed paths stay current.
 */
export function installMonacoProjectTypes(monaco: Monaco, getIndexedFilePaths: () => Set<string>): void {
  try {
    const tsDefaults = monaco.languages.typescript.typescriptDefaults;
    const jsDefaults = monaco.languages.typescript.javascriptDefaults;

    const sharedCompilerOptions: Parameters<typeof tsDefaults.setCompilerOptions>[0] = {
      // Mirror frontend/tsconfig.app.json so Monaco diagnostics match the real build.
      target: monaco.languages.typescript.ScriptTarget.ES2020,
      module: monaco.languages.typescript.ModuleKind.ESNext,
      // Monaco's TS worker is more stable with NodeJs resolution for virtual models.
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

    tsDefaults.setDiagnosticsOptions({
      noSemanticValidation: false,
      noSyntaxValidation: false,
    });

    jsDefaults.setDiagnosticsOptions({
      noSemanticValidation: false,
      noSyntaxValidation: false,
    });

    tsDefaults.setEagerModelSync(true);
    jsDefaults.setEagerModelSync(true);

    const reactTypes = getMonacoReactViteAmbientSource();

    // Refresh Monaco extra libs on each mount to avoid stale worker cache
    // holding old ambient declarations between project/editor reloads.
    for (const disposable of monacoTypeLibDisposables) {
      disposable.dispose();
    }
    monacoTypeLibDisposables = [
      tsDefaults.addExtraLib(reactTypes, MONACO_REACT_VITE_DTS_URI),
      jsDefaults.addExtraLib(reactTypes, MONACO_REACT_VITE_JS_DTS_URI),
    ];

    if (!monacoImportDefinitionProviderInitialized) {
      const definitionProvider = {
        provideDefinition(model: editor.ITextModel, position: IPosition) {
          const word = model.getWordAtPosition(position);
          if (!word?.word) return null;

          const importPath = findImportedModuleForSymbol(model.getValue(), word.word);
          if (!importPath) return null;

          const currentPath = normalizeProjectPath(decodeURIComponent(model.uri.path));
          const targetPath = resolveRelativeImportPath(currentPath, importPath, getIndexedFilePaths());
          if (!targetPath) return null;

          const uri = monaco.Uri.parse(toMonacoUri(targetPath));
          return {
            uri,
            range: new monaco.Range(1, 1, 1, 1),
          };
        },
      };

      monaco.languages.registerDefinitionProvider('typescript', definitionProvider);
      monaco.languages.registerDefinitionProvider('javascript', definitionProvider);
      monacoImportDefinitionProviderInitialized = true;
    }
  } catch (err) {
    console.error('Monaco types init failed, will retry on next mount:', err);
    for (const disposable of monacoTypeLibDisposables) {
      disposable.dispose();
    }
    monacoTypeLibDisposables = [];
    monacoImportDefinitionProviderInitialized = false;
  }
}
