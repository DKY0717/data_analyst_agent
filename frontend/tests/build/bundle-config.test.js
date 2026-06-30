import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '../..')

function readProjectFile(path) {
  return readFileSync(resolve(root, path), 'utf-8')
}

describe('frontend bundle configuration', () => {
  it('does not register the full Element Plus plugin in production entry', () => {
    const main = readProjectFile('src/main.js')

    expect(main).not.toContain("import ElementPlus from 'element-plus'")
    expect(main).not.toContain('app.use(ElementPlus')
    expect(main).toContain("element-plus/es/components/button/index.mjs")
  })

  it('keeps manual chunking scoped to actual heavy libraries', () => {
    const viteConfig = readProjectFile('vite.config.js')

    expect(viteConfig).not.toContain("'vendor-element': ['element-plus']")
    expect(viteConfig).toContain("id.includes('/element-plus/')")
    expect(viteConfig).toContain("id.includes('/xlsx/')")
  })
})
