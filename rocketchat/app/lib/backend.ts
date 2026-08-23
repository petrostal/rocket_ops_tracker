import { IHttp, IRead } from '@rocket.chat/apps-engine/definition/accessors';
import { IUser } from '@rocket.chat/apps-engine/definition/users';

export interface BackendResponse<T> {
  ok: boolean;
  status: number;
  data: T;
}

export function appUser(user: IUser) {
  return {
    rocket_chat_user_id: user.id,
    username: user.username,
    display_name: user.name || user.username,
  };
}

function validatedBackendUrl(value: unknown): string {
  const raw = String(value || '').replace(/\/$/, '');
  if (!raw) throw new Error('OpsTracker backend URL is not configured');
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch (_error) {
    throw new Error('OpsTracker backend URL is invalid');
  }
  const loopback = ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname);
  if (parsed.protocol !== 'https:' && !(parsed.protocol === 'http:' && loopback)) {
    throw new Error('OpsTracker backend URL must use HTTPS');
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error('OpsTracker backend URL must not contain credentials, query, or fragment');
  }
  return raw;
}

export async function callBackend<T>(read: IRead, http: IHttp, path: string, payload: unknown): Promise<BackendResponse<T>> {
  const settings = read.getEnvironmentReader().getSettings();
  const backendUrl = validatedBackendUrl(await settings.getValueById('backend_url'));
  const secret = String(await settings.getValueById('integration_secret'));
  const placeholder = /(change-me|changeme|development-|example|generate-|placeholder|replace-|test-|your-)/i;
  if (secret.length < 32 || placeholder.test(secret)) {
    throw new Error('OpsTracker integration secret must be a deployment-specific random value');
  }
  const timestamp = Math.floor(Date.now() / 1000).toString();
  const nonce = `${timestamp}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  const response = await http.post(`${backendUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      'X-OpsTracker-Secret': secret,
      'X-OpsTracker-Timestamp': timestamp,
      'X-OpsTracker-Nonce': nonce,
    },
    data: payload,
  });
  return { ok: response.statusCode >= 200 && response.statusCode < 300, status: response.statusCode, data: response.data as T };
}
