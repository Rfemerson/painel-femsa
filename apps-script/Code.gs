/** API somente leitura. Configure API_TOKEN e SPREADSHEET_ID nas propriedades. */
function json_(payload) {
  return ContentService.createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return json_({ok: false, error: 'Método não permitido. Utilize POST.'});
}

function doPost(e) {
  const properties = PropertiesService.getScriptProperties();
  const expected = properties.getProperty('API_TOKEN');
  let body;
  try {
    body = JSON.parse(e && e.postData ? e.postData.contents : '');
  } catch (_) {
    return json_({ok: false, error: 'Requisição inválida.'});
  }
  if (!expected || !body || typeof body.token !== 'string' || body.token !== expected) {
    return json_({ok: false, error: 'Acesso não autorizado.'});
  }
  try {
    // A planilha ativa não está disponível no contexto de uma aplicação web.
    // O ID deve ser o da planilha à qual este projeto está vinculado.
    const id = properties.getProperty('SPREADSHEET_ID');
    if (!id) return json_({ok: false, error: 'API não configurada.'});
    const spreadsheet = SpreadsheetApp.openById(id);
    const sheet = spreadsheet.getSheetByName('Base_Painel');
    if (!sheet) return json_({ok: false, error: 'Aba Base_Painel não encontrada.'});
    const values = sheet.getDataRange().getValues();
    const display = sheet.getDataRange().getDisplayValues();
    const headers = display[0].map(value => value.trim());
    if (headers.some(value => !value) || new Set(headers).size !== headers.length) {
      return json_({ok: false, error: 'Cabeçalhos vazios ou duplicados.'});
    }
    const timezone = spreadsheet.getSpreadsheetTimeZone();
    const records = values.slice(1).map((row, index) => ({row, index}))
      .filter(item => item.row.some(value => value !== ''))
      .map(item => {
        const record = Object.create(null);
        headers.forEach((header, column) => {
          const value = item.row[column];
          record[header] = value instanceof Date
            ? Utilities.formatDate(value, timezone, "yyyy-MM-dd'T'HH:mm:ss")
            : display[item.index + 1][column];
        });
        return record;
      });
    return json_({ok: true, records: records});
  } catch (_) {
    return json_({ok: false, error: 'Não foi possível consultar a base.'});
  }
}
