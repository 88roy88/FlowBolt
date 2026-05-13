import { authSession } from '../auth';

export async function readDataSourceAuthorization(): Promise<string | undefined> {
  return authSession.ensureFreshToken();
}
