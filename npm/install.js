#!/usr/bin/env node

// Downloads the correct Foundry binary from GitHub Releases during npm install.

const https = require("https");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const os = require("os");
const zlib = require("zlib");

const VERSION = "0.5.2";
const REPO = "context-foundry/context-foundry";

function getTarget() {
  const platform = os.platform();
  const arch = os.arch();

  if (platform === "darwin" && arch === "arm64") return "aarch64-apple-darwin";
  if (platform === "darwin" && arch === "x64") return "x86_64-apple-darwin";
  if (platform === "linux" && arch === "x64") return "x86_64-unknown-linux-gnu";
  if (platform === "win32" && arch === "x64") return "x86_64-pc-windows-msvc";

  throw new Error(`Unsupported platform: ${platform}-${arch}`);
}

function getBinaryName() {
  return os.platform() === "win32" ? "foundry.exe" : "foundry";
}

function getArchiveExt() {
  return os.platform() === "win32" ? "zip" : "tar.gz";
}

function fetch(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, { headers: { "User-Agent": "context-foundry-npm" } }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return fetch(res.headers.location).then(resolve, reject);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
        }
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => resolve(Buffer.concat(chunks)));
        res.on("error", reject);
      })
      .on("error", reject);
  });
}

async function extractTarGz(buffer, destDir, binaryName) {
  const tmpFile = path.join(os.tmpdir(), `foundry-${Date.now()}.tar.gz`);
  fs.writeFileSync(tmpFile, buffer);
  execSync(`tar xzf "${tmpFile}" -C "${destDir}"`, { stdio: "ignore" });
  fs.unlinkSync(tmpFile);

  const extracted = path.join(destDir, binaryName);
  if (!fs.existsSync(extracted)) {
    // Some archives nest in a directory
    const entries = fs.readdirSync(destDir);
    for (const entry of entries) {
      const nested = path.join(destDir, entry, binaryName);
      if (fs.existsSync(nested)) {
        fs.renameSync(nested, extracted);
        break;
      }
    }
  }
  return extracted;
}

async function extractZip(buffer, destDir, binaryName) {
  const tmpFile = path.join(os.tmpdir(), `foundry-${Date.now()}.zip`);
  fs.writeFileSync(tmpFile, buffer);

  if (os.platform() === "win32") {
    execSync(
      `powershell -Command "Expand-Archive -Path '${tmpFile}' -DestinationPath '${destDir}' -Force"`,
      { stdio: "ignore" }
    );
  } else {
    execSync(`unzip -o "${tmpFile}" -d "${destDir}"`, { stdio: "ignore" });
  }
  fs.unlinkSync(tmpFile);

  const extracted = path.join(destDir, binaryName);
  if (!fs.existsSync(extracted)) {
    const entries = fs.readdirSync(destDir);
    for (const entry of entries) {
      const nested = path.join(destDir, entry, binaryName);
      if (fs.existsSync(nested)) {
        fs.renameSync(nested, extracted);
        break;
      }
    }
  }
  return extracted;
}

async function main() {
  const target = getTarget();
  const binaryName = getBinaryName();
  const ext = getArchiveExt();
  const archiveName = `foundry-${target}.${ext}`;
  const url = `https://github.com/${REPO}/releases/download/v${VERSION}/${archiveName}`;

  const binDir = path.join(__dirname, "bin");
  const nativeName = os.platform() === "win32" ? "foundry-native.exe" : "foundry-native";
  const destPath = path.join(binDir, nativeName);

  // Skip if binary already exists and is the right version
  if (fs.existsSync(destPath)) {
    try {
      const version = execSync(`"${destPath}" --version`, { encoding: "utf8" }).trim();
      if (version.includes(VERSION)) {
        console.log(`foundry v${VERSION} already installed.`);
        return;
      }
    } catch {
      // Version check failed, re-download
    }
  }

  console.log(`Downloading foundry v${VERSION} for ${target}...`);

  const buffer = await fetch(url);
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "foundry-"));

  if (ext === "tar.gz") {
    await extractTarGz(buffer, tmpDir, binaryName);
  } else {
    await extractZip(buffer, tmpDir, binaryName);
  }

  const extractedBinary = path.join(tmpDir, binaryName);
  if (!fs.existsSync(extractedBinary)) {
    throw new Error(`Binary not found after extraction in ${tmpDir}`);
  }

  if (!fs.existsSync(binDir)) {
    fs.mkdirSync(binDir, { recursive: true });
  }

  fs.copyFileSync(extractedBinary, destPath);

  if (os.platform() !== "win32") {
    fs.chmodSync(destPath, 0o755);
  }

  // Clean up
  fs.rmSync(tmpDir, { recursive: true, force: true });

  console.log(`foundry v${VERSION} installed successfully.`);
}

main().catch((err) => {
  console.error(`Failed to install foundry: ${err.message}`);
  console.error("You can install manually from: https://github.com/context-foundry/context-foundry/releases");
  process.exit(1);
});
