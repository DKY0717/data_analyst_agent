import { spawn, spawnSync } from 'node:child_process'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(scriptDir, '..')
const projectDir = path.resolve(frontendDir, '..')
const backendDir = path.join(projectDir, 'backend')
const isWindows = process.platform === 'win32'

const serverEnv = {
  ...process.env,
  FORCE_COLOR: '1',
  // E2E 托管后端使用 8001，避免和开发者本地 8000 服务冲突。
  VITE_API_PROXY_TARGET: 'http://localhost:8001',
}

const children = []

function startProcess(label, command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    env: serverEnv,
    stdio: 'inherit',
    windowsHide: true,
  })

  child.once('exit', (code, signal) => {
    if (code !== null && code !== 0) {
      console.error(`[e2e:${label}] exited with code ${code}`)
    }
    if (signal) {
      console.error(`[e2e:${label}] exited with signal ${signal}`)
    }
  })

  children.push({ label, child })
  return child
}

function waitForUrl(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs

  return new Promise((resolve, reject) => {
    const probe = () => {
      const request = http.get(url, (response) => {
        response.resume()
        resolve()
      })

      request.on('error', () => {
        if (Date.now() >= deadline) {
          reject(new Error(`Timed out waiting for ${url}`))
          return
        }
        setTimeout(probe, 500)
      })

      request.setTimeout(1000, () => {
        request.destroy()
      })
    }

    probe()
  })
}

function waitForExit(child, timeoutMs = 3000) {
  if (child.exitCode !== null || child.killed) return Promise.resolve()

  return new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs)
    const finish = () => {
      clearTimeout(timer)
      resolve()
    }

    child.once('exit', finish)
    child.once('close', finish)
  })
}

async function stopProcessTree(label, child) {
  if (!child.pid) return

  console.log(`[e2e] stopping ${label} (${child.pid})`)

  try {
    child.kill('SIGTERM')
  } catch {
    // 进程可能已经自然退出。
  }

  await waitForExit(child, 1000)

  // Windows 下再补一刀，避免子进程树残留。
  if (isWindows && child.exitCode === null) {
    spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
    await waitForExit(child, 2000)
  }

  child.unref()
}

async function runPlaywright(args) {
  const playwrightCli = path.join(frontendDir, 'node_modules', '@playwright', 'test', 'cli.js')

  return new Promise((resolve) => {
    let resolved = false
    const child = spawn(process.execPath, [playwrightCli, 'test', ...args], {
      cwd: frontendDir,
      stdio: 'inherit',
      windowsHide: true,
      env: {
        ...process.env,
        E2E_MANAGED_SERVERS: '1',
      },
    })

    const finish = (code) => {
      if (resolved) return
      resolved = true
      resolve(code ?? 1)
    }

    child.once('close', finish)
    child.once('exit', finish)
  })
}

async function main() {
  const args = process.argv.slice(2)

  // 先启动真实后端和 Vite，E2E 内部仍可按用例选择是否 Mock 接口。
  startProcess('backend', 'python', ['-m', 'uvicorn', 'app.main:app', '--port', '8001'], backendDir)
  startProcess('frontend', process.execPath, [path.join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '0.0.0.0'], frontendDir)

  try {
    await Promise.all([
      waitForUrl('http://127.0.0.1:8001/health', 30000),
      waitForUrl('http://127.0.0.1:3000', 30000),
    ])

    const exitCode = await runPlaywright(args)
    process.exitCode = exitCode
  } finally {
    console.log('[e2e] cleaning up managed servers')
    for (const { label, child } of children.reverse()) {
      await stopProcessTree(label, child)
    }
  }
}

main().catch(async (error) => {
  console.error(error)
  process.exitCode = 1
  for (const { label, child } of children.reverse()) {
    await stopProcessTree(label, child)
  }
})
