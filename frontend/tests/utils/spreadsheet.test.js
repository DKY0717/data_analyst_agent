import { describe, expect, it } from 'vitest'

import { buildCsv, buildSpreadsheetXml } from '@/utils/spreadsheet'


describe('spreadsheet export', () => {
  it('escapes XML and forces user-controlled formulas to text', () => {
    const xml = buildSpreadsheetXml(['name', 'value'], [['<admin>', '=2+2']])

    expect(xml).toContain('&lt;admin&gt;')
    expect(xml).toContain('<Data ss:Type="String">&apos;=2+2</Data>')
    expect(xml).not.toContain('<Data ss:Type="Formula">')
  })

  it('neutralizes CSV formulas and quotes delimiters', () => {
    const csv = buildCsv(['name', 'value'], [['Alice, Bob', '@SUM(A1:A2)']])

    expect(csv).toContain('"Alice, Bob"')
    expect(csv).toContain("'@SUM(A1:A2)")
  })

  it('removes XML 1.0 control characters', () => {
    expect(buildSpreadsheetXml(['value'], [['a\u0000b']])).toContain('>ab<')
  })
})
