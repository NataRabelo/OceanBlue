(() => {
  let cursor = null;
  const status = document.getElementById('audit-status');
  const next = document.getElementById('audit-next');
  async function load(appendCursor) {
    next.disabled = true;
    const params = new URLSearchParams({limit: '50'});
    const company = document.getElementById('audit-company').value;
    if (company) params.set('empresa_id', company);
    if (appendCursor && cursor) params.set('before', cursor);
    try {
      const response = await fetch(`/api/auditoria/?${params}`);
      if (!response.ok) throw new Error('Consulta indisponível. Confira seu acesso e tente novamente.');
      const payload = await response.json();
      const rows = document.getElementById('audit-rows');
      rows.replaceChildren();
      for (const record of payload.data) {
        const row = document.createElement('tr');
        for (const key of ['criado_em', 'empresa_id', 'action', 'status', 'request_id']) {
          const cell = document.createElement('td');
          cell.textContent = record[key] ?? '—';
          row.append(cell);
        }
        rows.append(row);
      }
      cursor = payload.next_cursor;
      next.disabled = !cursor;
      status.textContent = `${payload.data.length} eventos nesta página.`;
    } catch (error) { status.textContent = error.message; }
  }
  document.getElementById('audit-filter').addEventListener('submit', event => { event.preventDefault(); load(false); });
  next.addEventListener('click', () => load(true));
  load(false);
})();
