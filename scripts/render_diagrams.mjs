/** Render repository Mermaid sources to PNG without sending diagram data to a third party. */
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, join } from "node:path";
import { pathToFileURL } from "node:url";

const root = process.cwd();
const diagrams = join(root, "docs", "diagrams");
const rendererDir = join(root, ".diagram-renderer");
const localCli = join(rendererDir, "node_modules", ".bin", process.platform === "win32" ? "mmdc.cmd" : "mmdc");
const edge = process.env.EDGE_PATH || "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

function escapeHtml(value) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function findVsCodeBundle() {
  if (process.env.MERMAID_BUNDLE && existsSync(process.env.MERMAID_BUNDLE)) return process.env.MERMAID_BUNDLE;
  const extensions = join(homedir(), ".vscode", "extensions");
  if (!existsSync(extensions)) return null;
  const match = readdirSync(extensions).find((name) => name.startsWith("mermaidchart.vscode-mermaid-chart-"));
  const bundle = match && join(extensions, match, "dist-sidebar", "mermaid.js");
  return bundle && existsSync(bundle) ? bundle : null;
}

function renderWithVsCodeBundle(source, output) {
  const bundle = findVsCodeBundle();
  if (!bundle || !existsSync(edge)) return false;
  mkdirSync(rendererDir, { recursive: true });
  const page = join(rendererDir, `${basename(output, ".png")}.render.html`);
  const document = `<!doctype html><meta charset="utf-8"><style>body{margin:24px;background:#fff}.mermaid{width:max-content;min-width:100%}</style><div class="mermaid">${escapeHtml(readFileSync(source, "utf8"))}</div><script src="${pathToFileURL(bundle).href}"></script><script>window.addEventListener("load",async()=>{try{await window.sidebarMermaid.run({nodes:[document.querySelector('.mermaid')]});document.body.dataset.rendered='true'}catch(error){document.body.dataset.error=String(error)}})</script>`;
  writeFileSync(page, document, "utf8");
  try {
    execFileSync(edge, ["--headless=new", "--disable-gpu", "--allow-file-access-from-files", "--virtual-time-budget=10000", "--window-size=1800,1200", `--screenshot=${output}`, pathToFileURL(page).href], { stdio: "inherit" });
    return existsSync(output);
  } finally {
    rmSync(page, { force: true });
  }
}

for (const filename of readdirSync(diagrams).filter((name) => name.endsWith(".mmd"))) {
  const source = join(diagrams, filename);
  const output = join(diagrams, filename.replace(/\.mmd$/, ".png"));
  if (existsSync(localCli)) {
    execFileSync(localCli, ["-i", source, "-o", output, "-b", "transparent"], { stdio: "inherit", shell: process.platform === "win32" });
  } else if (!renderWithVsCodeBundle(source, output)) {
    const npmCache = join(tmpdir(), "shifa-mermaid-npm");
    mkdirSync(npmCache, { recursive: true });
    execFileSync(process.platform === "win32" ? "npx.cmd" : "npx", ["--yes", "--cache", npmCache, "@mermaid-js/mermaid-cli", "-i", source, "-o", output, "-b", "transparent"], { stdio: "inherit", shell: process.platform === "win32" });
  }
  console.log(`Rendered ${filename} -> ${basename(output)}`);
}
