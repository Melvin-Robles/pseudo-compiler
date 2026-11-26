const state = { programs: {}, errorCases: {}, selectedProgram: '', selectedError: '', sourceMode: 'custom', target: 'python', result: null, activeOutput: 'code', testSession: null, sourceErrors: [] };
let inputAttentionTimer = null;

const $ = (id) => document.getElementById(id);
const editor = $('sourceEditor');
function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}
const DEFAULT_ERROR_CASES = {
  LEXICO: {
    label: 'Error léxico', description: 'Símbolo inválido', filename: 'caso_error_lexico.psc',
    source: `Inicio
    Escribir "Calculadora de áreas"
    Leer base, altura
    Dimension medidas[3]
    medidas[1] = base
    medidas[2] = altura
    area = (base * altura) @ 2
    Si area > 0 Entonces
        Escribir "Área válida: ", area
    FinSi
Fin`
  },
  SINTACTICO: {
    label: 'Error sintáctico', description: 'Cierre incorrecto', filename: 'caso_error_sintactico.psc',
    source: `Inicio
    Escribir "Validador de calificaciones"
    Leer nota
    Si nota >= 6 Entonces
        Escribir "Aprobado"
        Para i = 1 Hasta 3 Hacer
            Escribir "Intento ", i
        FinSi
    Sino
        Escribir "Reprobado"
    FinSi
Fin`
  },
  SEMANTICO: {
    label: 'Error semántico', description: 'Tipos y declaraciones', filename: 'caso_error_semantico.psc',
    source: `Inicio
    Escribir "Resumen de estudiante"
    Dimension notas[3]
    notas[1] = 8
    notas[2] = 9
    notas[3] = 10
    total = estudiante
    Si total Entonces
        Escribir "El total es lógico"
    FinSi
    promedio = "sin calcular" / 2
    notas["primera"] = 7
    Escribir "Promedio: ", promedio
Fin`
  }
};

async function api(path, options = {}) {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'No se pudo completar la operación');
  return data;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

function renderSourceMarkers(errors = state.sourceErrors) {
  state.sourceErrors = errors || [];
  const lines = editor.value.split('\n');
  const errorsByLine = new Map();
  state.sourceErrors.forEach((error) => {
    const line = Number(error.line);
    if (!errorsByLine.has(line)) errorsByLine.set(line, []);
    errorsByLine.get(line).push(error);
  });
  $('lineNumbers').innerHTML = lines.map((_, index) => {
    const line = index + 1;
    const lineErrors = errorsByLine.get(line) || [];
    const title = lineErrors.map((error) => `${error.category}: ${error.message}`).join(' | ');
    return `<span class="line-number${lineErrors.length ? ' has-error' : ''}"${title ? ` title="${escapeHtml(title)}"` : ''}><span>${line}</span></span>`;
  }).join('');
  $('sourceHighlights').innerHTML = lines.map((_, index) => `<span class="source-highlight-line${errorsByLine.has(index + 1) ? ' has-error' : ''}"></span>`).join('');
  $('sourceHighlights').style.transform = `translateY(${-editor.scrollTop}px)`;
}

function updateLineNumbers() {
  renderSourceMarkers();
}

function setStatus() {}

function setMobileMenu(open) {
  document.body.classList.toggle('mobile-menu-open', open);
  const button = $('mobileMenuButton');
  const backdrop = $('mobileSidebarBackdrop');
  if (button) {
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    button.innerHTML = `<i data-lucide="${open ? 'x' : 'menu'}"></i>`;
  }
  if (backdrop) backdrop.setAttribute('aria-hidden', String(!open));
  refreshIcons();
}

function closeMobileSidebar() {
  setMobileMenu(false);
}

function displayName(program) { return `programa_${program.toLowerCase()}.psc`; }

function renderPrograms() {
  const list = $('programList');
  const select = $('programSelect');
  list.innerHTML = '';
  select.innerHTML = '<option value="">Nueva compilación</option>';
  Object.keys(state.programs).forEach((program) => {
    const item = document.createElement('button');
    item.className = `program-item ${program === state.selectedProgram ? 'active' : ''}`;
    item.innerHTML = `<span class="psc-dot"></span> Programa ${program}`;
    item.onclick = () => selectProgram(program);
    list.appendChild(item);
    const option = document.createElement('option');
    option.value = program;
    option.textContent = `Programa ${program}`;
    option.selected = program === state.selectedProgram;
    select.appendChild(option);
  });
  const errorGroup = document.createElement('optgroup');
  errorGroup.label = 'Casos de error';
  Object.entries(state.errorCases).forEach(([key, item]) => {
    const option = document.createElement('option');
    option.value = `error:${key}`;
    option.textContent = item.label;
    option.selected = key === state.selectedError;
    errorGroup.appendChild(option);
  });
  select.appendChild(errorGroup);
  renderErrorCases();
}

function renderErrorCases() {
  const list = $('errorList');
  list.innerHTML = '';
  Object.entries(state.errorCases).forEach(([key, item]) => {
    const button = document.createElement('button');
    button.className = `error-item ${key === state.selectedError ? 'active' : ''}`;
    button.innerHTML = `<span class="error-dot ${key.toLowerCase()}"></span><span><strong>${item.label}</strong><small>${item.description}</small></span>`;
    button.onclick = () => selectErrorCase(key);
    list.appendChild(button);
  });
  refreshIcons();
}

function selectProgram(program) {
  closeMobileSidebar();
  state.selectedProgram = program;
  state.selectedError = '';
  state.sourceMode = program ? 'example' : 'custom';
  editor.value = program ? (state.programs[program] || '') : '';
  $('programSelect').value = program;
  $('programChooser').classList.toggle('hidden', !program);
  const filename = program ? displayName(program) : 'nuevo_programa.psc';
  $('sourceName').textContent = filename;
  $('breadcrumbName').textContent = filename;
  $('sourceFormat').textContent = 'Pseudocódigo - UTF-8';
  renderPrograms();
  updateLineNumbers();
  clearCompilationOutput();
}

function selectErrorCase(caseKey) {
  const item = state.errorCases[caseKey];
  if (!item) return;
  closeMobileSidebar();
  state.selectedProgram = '';
  state.selectedError = caseKey;
  state.sourceMode = 'error';
  editor.value = item.source;
  $('programSelect').value = `error:${caseKey}`;
  $('programChooser').classList.remove('hidden');
  $('sourceName').textContent = item.filename;
  $('breadcrumbName').textContent = item.filename;
  $('sourceFormat').textContent = 'Caso de error - UTF-8';
  renderPrograms();
  updateLineNumbers();
  clearCompilationOutput('Compila este caso para ver el diagnóstico del compilador.');
}

function loadCustomSource(filename, source) {
  state.selectedProgram = '';
  state.selectedError = '';
  state.sourceMode = 'custom';
  editor.value = source;
  $('programSelect').value = '';
  $('programChooser').classList.add('hidden');
  $('sourceName').textContent = filename;
  $('breadcrumbName').textContent = filename;
  $('sourceFormat').textContent = `${filename.toLowerCase().endsWith('.txt') ? 'Texto importado' : 'Pseudocódigo importado'} - UTF-8`;
  renderPrograms();
  updateLineNumbers();
  clearCompilationOutput('Fuente cargada. Presiona Compilar salida para analizarla.');
  editor.focus();
}

async function readSourceFile(file) {
  const extension = file.name.split('.').pop()?.toLowerCase();
  if (!['txt', 'psc'].includes(extension)) {
    alert('Solo se admiten archivos .txt o .psc');
    return;
  }
  loadCustomSource(file.name, await file.text());
}

function updateDownloadButton() {
  $('downloadButton').innerHTML = `<i data-lucide="download"></i>Descargar .${state.target === 'python' ? 'py' : 'js'}`;
  refreshIcons();
}

function updateTryButton() {
  $('tryButton').disabled = !state.result?.generated_code;
}

function clearCompilationOutput(message = 'Escribe pseudocódigo y presiona Compilar salida.') {
  state.result = null;
  $('generatedCode').className = 'code-output empty-output';
  $('generatedCode').textContent = message;
  $('codeLineCount').textContent = '0 líneas';
  $('downloadButton').disabled = true;
  updateDownloadButton();
  updateTryButton();
  renderSourceMarkers([]);
  $('astOutput').textContent = 'El AST aparecerá después de compilar.';
  $('astCount').textContent = '0 nodos';
  renderSymbols([]);
  renderDiagnostics([]);
  renderOutputMode([]);
}

function renderSymbols(rows) {
  $('symbolCount').textContent = `${rows.length} símbolo${rows.length === 1 ? '' : 's'}`;
  $('symbolsOutput').innerHTML = rows.length ? rows.map((row) => `<tr><td>${row.name}</td><td>${row.category}</td><td>${row.type}</td></tr>`).join('') : '<tr><td colspan="3" class="muted-cell">Sin símbolos todavía</td></tr>';
}

function renderDiagnostics(errors) {
  $('errorCount').textContent = `${errors.length} error${errors.length === 1 ? '' : 'es'}`;
  if (!errors.length) {
    $('diagnosticsOutput').className = 'diagnostics-empty';
    $('diagnosticsOutput').innerHTML = '<span class="check-circle">✓</span><div><strong>Sin diagnósticos</strong><small>El código pasó lexer, parser y análisis semántico.</small></div>';
    return;
  }
  $('diagnosticsOutput').className = '';
  $('diagnosticsOutput').innerHTML = errors.map((error) => `<div class="diagnostic-error"><strong>${error.category} - línea ${error.line}, columna ${error.column}</strong><br>${error.message}<br><span>↳ ${error.suggestion || 'Revisa la instrucción indicada.'}</span></div>`).join('');
}

function renderOutputMode(errors) {
  const hasErrors = errors.length > 0;
  const generatedView = $('generatedOutputView');
  const diagnosticsView = $('outputDiagnostics');
  const inspectorGrid = document.querySelector('.inspector-grid');
  generatedView.classList.toggle('hidden', hasErrors);
  diagnosticsView.classList.toggle('hidden', !hasErrors);
  $('outputPanelTitle').textContent = hasErrors ? 'Diagnóstico' : 'Salida generada';
  $('targetBadge').classList.toggle('hidden', hasErrors);
  $('copyButton').classList.toggle('hidden', hasErrors);
  $('downloadButton').classList.toggle('hidden', hasErrors);
  $('tryButton').classList.toggle('hidden', hasErrors);
  if (inspectorGrid) inspectorGrid.classList.add('without-diagnostics');
  $('diagnosticsPanel').classList.add('hidden');
  if (!hasErrors) {
    diagnosticsView.innerHTML = '';
    return;
  }
  diagnosticsView.innerHTML = `<div class="output-diagnostics-heading"><span class="diagnostic-alert">!</span><div><strong>Corrige los problemas detectados</strong><small>${errors.length} diagnóstico${errors.length === 1 ? '' : 's'} antes de generar la salida</small></div><button id="downloadErrorsButton" class="download-errors-button"><i data-lucide="file-down"></i>Descargar errores .txt</button></div>${errors.map((error) => `<article class="output-diagnostic-item"><div class="output-diagnostic-meta">${error.category} - línea ${error.line}, columna ${error.column}</div><strong>${error.message}</strong><p>${error.suggestion || 'Revisa la instrucción indicada.'}</p></article>`).join('')}`;
  refreshIcons();
  $('downloadErrorsButton').onclick = downloadErrors;
}

function downloadErrors() {
  const errors = state.result?.errors || [];
  if (!errors.length) return;
  const lines = [
    'PSEUDOCOMPILER IDE — DIAGNÓSTICO DE COMPILACIÓN',
    `Archivo: ${$('sourceName').textContent}`,
    `Total de errores: ${errors.length}`,
    '',
  ];
  errors.forEach((error, index) => {
    lines.push(`${index + 1}. ${String(error.category).toUpperCase()}`);
    lines.push(`   Ubicación: línea ${error.line}, columna ${error.column}`);
    lines.push(`   Mensaje: ${error.message}`);
    lines.push(`   Sugerencia: ${error.suggestion || 'Revisa la instrucción indicada.'}`);
    lines.push('');
  });
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${$('sourceName').textContent.replace(/\.(psc|txt)$/i, '')}_errores.txt`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function renderResult(result) {
  state.result = result;
  const success = result.success;
  $('targetBadge').textContent = state.target === 'python' ? 'PY' : 'JS';
  $('downloadButton').disabled = !result.generated_code;
  updateDownloadButton();
  updateTryButton();
  $('codeLineCount').textContent = result.generated_code ? `${result.generated_code.split('\n').length - 1} líneas` : '0 líneas';
  $('generatedCode').className = result.generated_code ? 'code-output' : 'code-output empty-output';
  $('generatedCode').textContent = result.generated_code || 'No hay código de salida porque la fuente contiene errores.';
  $('astOutput').textContent = result.ast_tree || 'AST vacío';
  $('astCount').textContent = `${countAstNodes(result.ast)} nodos`;
  renderSymbols(result.symbols || []);
  const errors = result.errors || [];
  renderDiagnostics(errors);
  renderSourceMarkers(errors);
  renderOutputMode(errors);
}

function invalidateOutput() {
  state.result = null;
  $('targetBadge').textContent = state.target === 'python' ? 'PY' : 'JS';
  $('generatedCode').className = 'code-output empty-output';
  $('generatedCode').textContent = 'Cambia el lenguaje de destino y presiona Compilar salida para generar el nuevo archivo.';
  $('codeLineCount').textContent = '0 líneas';
  $('downloadButton').disabled = true;
  updateDownloadButton();
  updateTryButton();
  renderOutputMode([]);
  setStatus('idle', 'Recompila para actualizar');
}

async function openTestModal() {
  if (!state.result?.generated_code) return;
  const isPython = state.target === 'python';
  $('testModal').classList.remove('hidden');
  $('testModal').setAttribute('aria-hidden', 'false');
  $('testGeneratedCode').textContent = state.result.generated_code;
  $('testCodeTitle').textContent = isPython ? 'Código Python' : 'Código JavaScript';
  $('testCodeMeta').textContent = `${$('sourceName').textContent} - salida generada`;
  $('testTargetBadge').textContent = isPython ? 'PY' : 'JS';
  $('testConsoleOutput').className = 'test-console-output';
  $('testConsoleOutput').textContent = 'Iniciando programa…';
  $('testRunStatus').className = 'console-status';
  $('testRunStatus').textContent = 'Iniciando';
  $('testConsoleInput').value = '';
  $('testConsoleInput').disabled = true;
  $('sendTestInput').disabled = true;
  state.testSession = { inputs: [], backendOutput: '', display: '' };
  await runTestSession();
}

function closeTestModal() {
  clearInputAttention();
  $('testModal').classList.add('hidden');
  $('testModal').setAttribute('aria-hidden', 'true');
}

function clearInputAttention() {
  if (inputAttentionTimer) {
    window.clearTimeout(inputAttentionTimer);
    inputAttentionTimer = null;
  }
  $('terminalInputRow')?.classList.remove('attention');
}

function highlightTestInput() {
  const row = $('terminalInputRow');
  if (!row) return;
  if (inputAttentionTimer) window.clearTimeout(inputAttentionTimer);
  row.classList.remove('attention');
  void row.offsetWidth;
  row.classList.add('attention');
  inputAttentionTimer = window.setTimeout(() => {
    row.classList.remove('attention');
    inputAttentionTimer = null;
  }, 2200);
}

async function runTestSession(nextInput = null) {
  if (!state.result?.generated_code) return;
  const session = state.testSession || { inputs: [], backendOutput: '', display: '' };
  state.testSession = session;
  if (nextInput !== null) {
    session.inputs.push(nextInput);
    session.display += `${session.display ? '\n' : ''}${nextInput}`;
  }
  $('testRunStatus').className = 'console-status';
  $('testRunStatus').textContent = 'Ejecutando';
  $('testConsoleInput').disabled = true;
  $('sendTestInput').disabled = true;
  try {
    const result = await api('/api/run', {
      method: 'POST',
      body: JSON.stringify({ code: state.result.generated_code, target: state.target, input_text: session.inputs.join('\n') }),
    });
    const output = String(result.output || '').replace(/\r/g, '');
    const previousOutput = session.backendOutput;
    const delta = output.startsWith(previousOutput) ? output.slice(previousOutput.length) : output;
    if (delta) session.display += delta;
    session.backendOutput = output;
    $('testConsoleOutput').textContent = session.display || '(sin salida)';
    if (result.success) {
      $('testConsoleOutput').className = 'test-console-output';
      $('testRunStatus').className = 'console-status success';
      $('testRunStatus').textContent = 'Ejecución correcta';
      clearInputAttention();
      $('testConsoleInput').placeholder = 'Programa finalizado';
    } else if (/Faltan datos de entrada/i.test(result.error || '')) {
      $('testConsoleOutput').className = 'test-console-output';
      $('testRunStatus').className = 'console-status';
      $('testRunStatus').textContent = 'Esperando entrada';
      $('testConsoleInput').disabled = false;
      $('sendTestInput').disabled = false;
      $('testConsoleInput').placeholder = 'Escribe un valor y presiona Enter';
      highlightTestInput();
      $('testConsoleInput').focus();
    } else {
      clearInputAttention();
      $('testConsoleOutput').className = 'test-console-output error-output';
      session.display += `${session.display ? '\n' : ''}${result.error || 'La ejecución terminó con error.'}`;
      $('testConsoleOutput').textContent = session.display;
      $('testRunStatus').className = 'console-status error';
      $('testRunStatus').textContent = 'Ejecución con error';
      $('testConsoleInput').placeholder = 'Corrige el código y vuelve a compilar';
    }
  } catch (error) {
    $('testConsoleOutput').className = 'test-console-output error-output';
    $('testConsoleOutput').textContent = error.message;
    $('testRunStatus').className = 'console-status error';
    $('testRunStatus').textContent = 'Error del servidor';
  }
}

function submitTestInput() {
  const input = $('testConsoleInput');
  const value = input.value;
  if (!value.trim() || input.disabled) return;
  input.value = '';
  runTestSession(value);
}

function countAstNodes(node) {
  if (!node || typeof node !== 'object') return 0;
  return 1 + Object.values(node).reduce((total, value) => total + (Array.isArray(value) ? value.reduce((sum, item) => sum + countAstNodes(item), 0) : countAstNodes(value)), 0);
}

async function compile() {
  const button = $('compileButton');
  button.disabled = true;
  button.innerHTML = '<i data-lucide="loader-circle"></i>Compilando…';
  refreshIcons();
  try {
    const result = await api('/api/compile', { method: 'POST', body: JSON.stringify({ source: editor.value, source_name: $('sourceName').textContent, target: state.target }) });
    renderResult(result);
  } catch (error) {
    setStatus('error', 'Error del servidor');
    $('diagnosticsOutput').innerHTML = `<div class="diagnostic-error">${error.message}</div>`;
  } finally {
    button.disabled = false;
    button.innerHTML = '<i data-lucide="play"></i>Compilar salida';
    refreshIcons();
  }
}

function renderSuite(data) {
  $('totalTests').textContent = data.total;
  $('passedTests').textContent = data.passed;
  $('failedTests').textContent = data.failed;
  $('passedPercent').textContent = `${Math.round((data.passed / data.total) * 100)}% del total`;
  $('suiteTarget').textContent = data.target === 'python' ? 'PY' : 'JS';
  $('suiteStatus').textContent = data.failed ? 'Revisión requerida' : 'Todos los casos correctos';
  $('testsOutput').innerHTML = data.cases.map((row) => `<tr><td><strong>${row.program}</strong></td><td>${row.case}</td><td>${row.inputs.join(', ')}</td><td>${row.expected.join(' - ')}</td><td><span class="${row.passed ? 'test-pass' : 'test-fail'}">${row.passed ? '✓ Correcto' : '× Falló'}</span></td><td>${row.detail}</td></tr>`).join('');
}

async function runTests() {
  const button = $('runTestsButton');
  button.disabled = true;
  button.innerHTML = '<i data-lucide="loader-circle"></i>Ejecutando…';
  refreshIcons();
  $('suiteStatus').textContent = `Ejecutando casos en ${state.target === 'python' ? 'Python' : 'JavaScript'}`;
  try { renderSuite(await api('/api/test-suite', { method: 'POST', body: JSON.stringify({ target: state.target }) })); }
  catch (error) { $('suiteStatus').textContent = error.message; }
  finally { button.disabled = false; button.innerHTML = '<i data-lucide="play"></i>Ejecutar pruebas'; refreshIcons(); }
}

function switchView(view) {
  closeMobileSidebar();
  document.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item.dataset.view === view));
  $('workbenchView').classList.toggle('active-view', view === 'workbench');
  $('testsView').classList.toggle('active-view', view === 'tests');
}

function wireEvents() {
  editor.addEventListener('input', () => { state.sourceErrors = []; updateLineNumbers(); });
  editor.addEventListener('scroll', () => { $('lineNumbers').scrollTop = editor.scrollTop; $('sourceHighlights').style.transform = `translateY(${-editor.scrollTop}px)`; });
  editor.addEventListener('keyup', () => { const before = editor.value.slice(0, editor.selectionStart).split('\n'); $('cursorInfo').textContent = `Línea ${before.length}, columna ${before[before.length - 1].length + 1}`; });
  $('uploadButton').onclick = () => $('sourceFileInput').click();
  $('sourceFileInput').onchange = (event) => { const file = event.target.files?.[0]; if (file) readSourceFile(file); event.target.value = ''; };
  const editorWrap = document.querySelector('.editor-wrap');
  editorWrap.addEventListener('dragover', (event) => { event.preventDefault(); editorWrap.classList.add('drop-active'); });
  editorWrap.addEventListener('dragleave', () => editorWrap.classList.remove('drop-active'));
  editorWrap.addEventListener('drop', (event) => { event.preventDefault(); editorWrap.classList.remove('drop-active'); const file = event.dataTransfer.files?.[0]; if (file) readSourceFile(file); });
  $('programSelect').onchange = (event) => event.target.value.startsWith('error:') ? selectErrorCase(event.target.value.slice(6)) : selectProgram(event.target.value);
  $('targetSelect').onchange = (event) => { state.target = event.target.value; $('suiteTarget').textContent = state.target === 'python' ? 'PY' : 'JS'; if (state.result?.generated_code) invalidateOutput(); };
  $('compileButton').onclick = compile;
  $('runTestsButton').onclick = runTests;
  $('tryButton').onclick = openTestModal;
  $('sendTestInput').onclick = submitTestInput;
  $('testConsoleInput').onkeydown = (event) => { if (event.key === 'Enter') { event.preventDefault(); submitTestInput(); } };
  $('closeTestModal').onclick = closeTestModal;
  document.querySelector('[data-close-test-modal]').onclick = closeTestModal;
  $('mobileMenuButton').onclick = () => setMobileMenu(!document.body.classList.contains('mobile-menu-open'));
  $('mobileSidebarBackdrop').onclick = closeMobileSidebar;
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') return;
    if (!$('testModal').classList.contains('hidden')) closeTestModal();
    else closeMobileSidebar();
  });
  $('clearButton').onclick = () => selectProgram('');
  $('createCompilationButton').onclick = () => { selectProgram(''); editor.focus(); };
  $('copyButton').onclick = async () => { if (state.result?.generated_code) { await navigator.clipboard.writeText(state.result.generated_code); $('copyButton').innerHTML = '<i data-lucide="check"></i>Copiado'; refreshIcons(); setTimeout(() => { $('copyButton').innerHTML = '<i data-lucide="copy"></i>Copiar código'; refreshIcons(); }, 1200); } };
  $('downloadButton').onclick = () => { if (!state.result?.generated_code) return; const extension = state.target === 'python' ? 'py' : 'js'; const blob = new Blob([state.result.generated_code], { type: 'text/plain;charset=utf-8' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${state.selectedProgram.toLowerCase() || 'nuevo_programa'}_generado.${extension}`; link.click(); URL.revokeObjectURL(link.href); };
  document.querySelectorAll('.nav-item').forEach((item) => { item.onclick = () => switchView(item.dataset.view); });
  refreshIcons();
}

async function boot() {
  wireEvents();
  try {
    const data = await api('/api/programs');
    state.programs = data.programs || {};
    state.errorCases = Object.keys(data.error_cases || {}).length ? data.error_cases : DEFAULT_ERROR_CASES;
    renderPrograms();
    selectProgram('');
  } catch (error) {
    state.errorCases = DEFAULT_ERROR_CASES;
    renderPrograms();
    renderErrorCases();
    setStatus('error', 'No se pudo cargar');
    $('sourceEditor').value = `Inicio\n    Escribir "${error.message}"\nFin`;
    updateLineNumbers();
  }
}

boot();
