import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

async function proxyToPython(request, path, payload) {
  const response = await fetch(new URL(path, request.url), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return new Response(await response.text(), {
    status: response.status,
    headers: { 'content-type': 'application/json; charset=utf-8' },
  });
}

export async function POST(request) {
  const payload = await request.json();
  if (String(payload.target || '').toLowerCase() === 'python') {
    return proxyToPython(request, '/api/run-python', payload);
  }
  if (String(payload.target || '').toLowerCase() !== 'javascript') {
    return Response.json({ error: 'Lenguaje no soportado' }, { status: 400 });
  }

  const folder = mkdtempSync(join(tmpdir(), 'pseudocompiler-'));
  const file = join(folder, 'salida.js');
  writeFileSync(file, String(payload.code || ''), 'utf8');
  const completed = spawnSync(process.execPath, [file], {
    input: String(payload.input_text || ''),
    encoding: 'utf8',
    timeout: 6000,
    maxBuffer: 1024 * 1024,
  });
  rmSync(folder, { recursive: true, force: true });

  const output = String(completed.stdout || '').trim();
  const error = String(completed.stderr || '').trim();
  return Response.json({
    success: completed.status === 0,
    output,
    error: completed.error?.code === 'ETIMEDOUT' ? 'El programa superó el límite de 6 segundos.' : error,
    target: 'javascript',
  });
}
