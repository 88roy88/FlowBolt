/** Readable form of a route reported by the preview toolbar; `/` means the app's home page. */
export function formatPreviewRoute(route: string): string {
  // HashRouter apps keep their route in the hash.
  const path = route.replace(/^\/#(?=\/)/, '');
  try {
    return decodeURI(path);
  } catch {
    return path;
  }
}
