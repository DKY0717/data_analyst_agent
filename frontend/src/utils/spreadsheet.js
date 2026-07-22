function sanitizeCell(value) {
  return Array.from(String(value ?? ''))
    .filter((character) => {
      const code = character.charCodeAt(0)
      return code >= 32 || code === 9 || code === 10 || code === 13
    })
    .join('')
}

function neutralizeFormula(value) {
  const text = sanitizeCell(value)
  return /^[=+\-@]/.test(text.trimStart()) ? `'${text}` : text
}

function escapeXml(value) {
  return neutralizeFormula(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;')
}

export function buildSpreadsheetXml(columns, rows) {
  // 所有值都声明为 String，避免用户可控结果被 Excel 当成公式执行。
  const rowXml = [columns, ...rows]
    .map((row) => {
      const cells = row
        .map((cell) => `<Cell><Data ss:Type="String">${escapeXml(cell)}</Data></Cell>`)
        .join('')
      return `<Row>${cells}</Row>`
    })
    .join('')

  return `<?xml version="1.0"?><?mso-application progid="Excel.Sheet"?>` +
    `<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" ` +
    `xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">` +
    `<Worksheet ss:Name="Sheet1"><Table>${rowXml}</Table></Worksheet></Workbook>`
}

export function buildCsv(columns, rows) {
  return [columns, ...rows]
    .map((row) => row.map((cell) => {
      const text = neutralizeFormula(cell)
      return /[,"\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
    }).join(','))
    .join('\n')
}
