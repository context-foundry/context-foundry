#!/usr/bin/env node

const fs = require("fs");
const path = require("path");

function collectStrings(value, out = []) {
  if (typeof value === "string") {
    out.push(value);
  } else if (Array.isArray(value)) {
    value.forEach((item) => collectStrings(item, out));
  } else if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectStrings(item, out));
  }
  return out;
}

function extractRefs(text, prefix) {
  const refs = new Set();
  if (!text) return refs;
  const regex = new RegExp(`\\${prefix}\\.(\\w+)`, "g");
  let match;
  while ((match = regex.exec(text)) !== null) {
    refs.add(match[1]);
  }
  return refs;
}

function extractOutputRefs(text) {
  const refs = new Set();
  if (!text) return refs;
  const regex = /\boutput\.(\w+)/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    refs.add(match[1]);
  }
  return refs;
}

function validateFlow(filePath) {
  const result = {
    file: filePath,
    ok: true,
    errors: [],
    warnings: []
  };

  let flow;
  try {
    flow = JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    result.ok = false;
    result.errors.push(`Invalid JSON: ${error.message}`);
    return result;
  }

  const nodes = flow.nodes || [];
  const edges = flow.edges || [];
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const incoming = new Set();
  const outputAnchors = new Map();
  const inputAnchors = new Map();

  for (const node of nodes) {
    outputAnchors.set(
      node.id,
      new Set(((node.data && node.data.outputAnchors) || []).map((anchor) => anchor.id))
    );
    inputAnchors.set(
      node.id,
      new Set(((node.data && node.data.inputAnchors) || []).map((anchor) => anchor.id))
    );
  }

  for (const edge of edges) {
    const label = edge.id || `${edge.source}->${edge.target}`;
    if (!nodeMap.has(edge.source)) {
      result.errors.push(`Edge "${label}" source node "${edge.source}" not found`);
    }
    if (!nodeMap.has(edge.target)) {
      result.errors.push(`Edge "${label}" target node "${edge.target}" not found`);
    }
    if (edge.sourceHandle && nodeMap.has(edge.source)) {
      const anchors = outputAnchors.get(edge.source);
      if (anchors.size > 0 && !anchors.has(edge.sourceHandle)) {
        result.errors.push(`Edge "${label}" sourceHandle "${edge.sourceHandle}" is not in source outputAnchors`);
      }
    }
    if (edge.targetHandle && nodeMap.has(edge.target)) {
      const anchors = inputAnchors.get(edge.target);
      if (anchors.size > 0 && !anchors.has(edge.targetHandle) && edge.targetHandle !== edge.target) {
        result.errors.push(`Edge "${label}" targetHandle "${edge.targetHandle}" is not in target inputAnchors`);
      }
      if (anchors.size === 0 && edge.targetHandle !== edge.target) {
        result.warnings.push(`Edge "${label}" targetHandle "${edge.targetHandle}" differs from target node ID "${edge.target}"`);
      }
    }
    if (nodeMap.has(edge.target)) {
      incoming.add(edge.target);
    }
  }

  for (const node of nodes) {
    const nodeType = (node.data && node.data.type) || "";
    const nodeName = (node.data && node.data.name) || "";
    const label = (node.data && node.data.label) || node.id;
    const isStart = nodeType === "Start" || nodeName === "startAgentflow";
    const isSticky = nodeType === "StickyNote" || nodeName === "stickyNoteAgentflow";
    if (!isStart && !isSticky && !incoming.has(node.id)) {
      result.errors.push(`Orphaned node "${label}" (${node.id}) has no incoming edges`);
    }
  }

  const startNode = nodes.find((node) => {
    const nodeType = (node.data && node.data.type) || "";
    const nodeName = (node.data && node.data.name) || "";
    return nodeType === "Start" || nodeName === "startAgentflow";
  });

  if (!startNode) {
    result.errors.push("No Start node found");
  }

  const startStateKeys = new Set(
    (((startNode || {}).data || {}).inputs || {}).startState
      ? (((startNode || {}).data || {}).inputs || {}).startState.map((entry) => entry.key).filter(Boolean)
      : []
  );
  const formInputNames = new Set(
    (((startNode || {}).data || {}).inputs || {}).formInputTypes
      ? (((startNode || {}).data || {}).inputs || {}).formInputTypes
          .flatMap((entry) => [entry.label, entry.name])
          .filter(Boolean)
      : []
  );

  const flowStateRefs = new Set();
  const formRefs = new Set();
  const stateWriteKeys = new Set();

  for (const node of nodes) {
    const text = collectStrings(((node.data || {}).inputs) || {}).join(" ");
    for (const ref of extractRefs(text, "$flow\\.state")) flowStateRefs.add(ref);
    for (const ref of extractRefs(text, "$form")) formRefs.add(ref);
    const updates = (((node.data || {}).inputs) || {}).llmUpdateState || [];
    for (const update of updates) {
      if (update.key) stateWriteKeys.add(update.key);
    }
  }

  for (const ref of flowStateRefs) {
    if (!startStateKeys.has(ref)) {
      result.errors.push(`$flow.state.${ref} is referenced but not declared in Start startState`);
    }
  }
  for (const ref of formRefs) {
    if (formInputNames.size > 0 && !formInputNames.has(ref)) {
      result.warnings.push(`$form.${ref} is referenced but not declared in Start formInputTypes`);
    }
  }
  for (const key of stateWriteKeys) {
    if (!startStateKeys.has(key)) {
      result.errors.push(`llmUpdateState writes key "${key}" but Start startState does not declare it`);
    }
  }

  for (const node of nodes) {
    const inputs = ((node.data || {}).inputs) || {};
    const structured = inputs.llmStructuredOutput || [];
    const updates = inputs.llmUpdateState || [];
    if (structured.length === 0) continue;

    const outputKeys = structured.map((entry) => entry.key).filter(Boolean);
    const referencedOutputKeys = new Set();
    for (const update of updates) {
      for (const ref of extractOutputRefs(update.value || "")) {
        referencedOutputKeys.add(ref);
      }
    }

    const label = ((node.data || {}).label) || node.id;
    for (const key of outputKeys) {
      if (!referencedOutputKeys.has(key)) {
        result.errors.push(`Node "${label}" does not wire llmStructuredOutput "${key}" into llmUpdateState`);
      }
    }
    for (const ref of referencedOutputKeys) {
      if (!outputKeys.includes(ref)) {
        result.errors.push(`Node "${label}" references output.${ref} in llmUpdateState without matching llmStructuredOutput`);
      }
    }
  }

  result.ok = result.errors.length === 0;
  return result;
}

function resolveFiles(argv) {
  if (argv.length > 0) return argv;
  const outputDir = path.join(process.cwd(), "output");
  if (!fs.existsSync(outputDir)) return [];
  return fs
    .readdirSync(outputDir)
    .filter((name) => name.endsWith(".json"))
    .sort()
    .map((name) => path.join(outputDir, name));
}

const files = resolveFiles(process.argv.slice(2));
if (files.length === 0) {
  console.error("No Flowise JSON files provided and none found in output/");
  process.exit(2);
}

const results = files.map(validateFlow);
process.stdout.write(JSON.stringify(results, null, 2) + "\n");
process.exit(results.some((result) => !result.ok) ? 1 : 0);
