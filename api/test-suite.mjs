import { readFileSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

const TEST_CASES = {
  A: [
    [[4, 2, 3], ['El resultado es: 16']],
    [[10, 5, 2], ['El resultado es: 28']],
    [[6, 3, 4], ['El resultado es: 34']],
  ],
  B: [
    [[8, 80], ['Aprobado']],
    [[7, 60], ['Reprobado por asistencia']],
    [[4, 90], ['Reprobado por nota']],
  ],
  C: [
    [[4], ['El factorial es: 24', 'La suma es: 20']],
    [[5], ['El factorial es: 120', 'La suma es: 30']],
    [[1], ['El factorial es: 1', 'La suma es: 2']],
  ],
  D: [
    [[3, 4, 9, 2], ['El promedio es: 5', 'El número mayor es: 9']],
    [[4, 10, 20, 5, 15], ['El promedio es: 12.5', 'El número mayor es: 20']],
    [[5, 1, 1, 1, 1, 1], ['El promedio es: 1', 'El número mayor es: 1']],
  ],
  E: [
    [[5, 4], ['El área es: 20', 'Clasificación: Pequeña']],
    [[10, 8], ['El área es: 80', 'Clasificación: Grande']],
    [[6, 9], ['El área es: 54', 'Clasificación: Grande']],
  ],
};

async function compileProgram(request, source, name) {
  const response = await fetch(new URL('/api/compile', request.url), {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ source, source_name: name, target: 'javascript' }),
  });
  return response.json();
}

function runGenerated(code, inputs) {
  const folder = mkdtempSync(join(tmpdir(), 'pseudocompiler-suite-'));
  const file = join(folder, 'salida.mjs');
  writeFileSync(file, code, 'utf8');
  const completed = spawnSync(process.execPath, [file], {
    input: `${inputs.join('\n')}\n`,
    encoding: 'utf8',
    timeout: 6000,
    maxBuffer: 1024 * 1024,
  });
  rmSync(folder, { recursive: true, force: true });
  return {
    ok: completed.status === 0,
    output: String(completed.stdout || '').trim().split(/\r?\n/).filter(Boolean),
    error: String(completed.stderr || '').trim(),
  };
}

export async function POST(request) {
  const payload = await request.json();
  const target = String(payload.target || '').toLowerCase();
  if (target === 'python') {
    const response = await fetch(new URL('/api/test-suite-python', request.url), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return new Response(await response.text(), {
      status: response.status,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }
  if (target !== 'javascript') {
    return Response.json({ error: 'Lenguaje no soportado' }, { status: 400 });
  }

  const rows = [];
  for (const [program, cases] of Object.entries(TEST_CASES)) {
    const filename = `programa_${program.toLowerCase()}.psc`;
    const source = readFileSync(join(process.cwd(), 'programas', filename), 'utf8');
    const compilation = await compileProgram(request, source, filename);
    for (let index = 0; index < cases.length; index += 1) {
      const [inputs, expected] = cases[index];
      if (!compilation.success) {
        rows.push({ program, case: index + 1, inputs, expected, actual: [], passed: false, detail: 'El programa no compila' });
        continue;
      }
      const result = runGenerated(compilation.generated_code, inputs);
      const passed = result.ok && expected.every((line) => result.output.includes(line));
      rows.push({
        program,
        case: index + 1,
        inputs,
        expected,
        actual: result.output,
        passed,
        detail: passed ? 'Salida coincide con el caso esperado' : (result.error || 'La salida no coincide'),
      });
    }
  }
  const passed = rows.filter((row) => row.passed).length;
  return Response.json({ target: 'javascript', total: rows.length, passed, failed: rows.length - passed, cases: rows });
}
