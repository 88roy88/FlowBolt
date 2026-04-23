import type { SearchResult, PackageMetadata } from '../schemas.js';
import type { MockPackage } from './package-base.js';
import { packageById } from './registry.js';

function pkgToSearchResult(pkg: MockPackage): SearchResult {
  return {
    Id: pkg.id,
    Name: pkg.name,
    Type: 'Package',
    Purpose: '',
    Description: pkg.description,
  };
}

export function searchPackages(query: string): SearchResult[] {
  const lowered = query.toLowerCase();

  if (/^\d+$/.test(query)) {
    const pkg = packageById.get(query);
    return pkg ? [pkgToSearchResult(pkg)] : [];
  }

  return Array.from(packageById.values())
    .filter((pkg) => pkg.name.toLowerCase().includes(lowered))
    .map(pkgToSearchResult);
}

export function getPackageFullMetadata(packageId: string): PackageMetadata | null {
  const numeric = Number(packageId);
  if (!Number.isFinite(numeric)) return null;

  const pkg = packageById.get(String(numeric));
  if (!pkg) return null;

  return pkg.metadata;
}
