/**
 * File tree parsing utilities.
 *
 * Converts flat file path lists into hierarchical tree structures.
 */

import { FileNode } from '../types/api'

/**
 * Parse array of file paths into hierarchical tree structure.
 *
 * @param paths - Array of file paths (e.g., ["src/App.tsx", "src/utils/helpers.ts"])
 * @returns Array of root-level FileNode objects
 */
export function parseFileTree(paths: string[]): FileNode[] {
  const root: FileNode = {
    path: '/',
    name: 'root',
    type: 'directory',
    children: [],
    expanded: true,
  }

  // Sort paths for consistent ordering
  const sortedPaths = [...paths].sort()

  for (const path of sortedPaths) {
    addPathToTree(root, path)
  }

  // Return children of root (not root itself)
  return root.children || []
}

/**
 * Add a single path to the tree.
 *
 * @param root - Root node
 * @param path - File path to add
 */
function addPathToTree(root: FileNode, path: string): void {
  const parts = path.split('/').filter(Boolean)
  let currentNode = root

  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]
    const isFile = i === parts.length - 1
    const fullPath = parts.slice(0, i + 1).join('/')

    // Ensure children array exists
    if (!currentNode.children) {
      currentNode.children = []
    }

    // Find or create child node
    let childNode = currentNode.children.find((child) => child.name === part)

    if (!childNode) {
      childNode = {
        path: fullPath,
        name: part,
        type: isFile ? 'file' : 'directory',
        expanded: false,
        children: isFile ? undefined : [],
      }

      currentNode.children.push(childNode)

      // Sort children: directories first, then alphabetically
      currentNode.children.sort((a, b) => {
        if (a.type !== b.type) {
          return a.type === 'directory' ? -1 : 1
        }
        return a.name.localeCompare(b.name)
      })
    }

    currentNode = childNode
  }
}

/**
 * Search file tree for nodes matching a query.
 *
 * @param node - Root node to search
 * @param query - Search query (case-insensitive)
 * @returns Array of matching file paths
 */
export function searchFileTree(node: FileNode, query: string): string[] {
  const results: string[] = []
  const lowerQuery = query.toLowerCase()

  function traverse(node: FileNode) {
    if (node.name.toLowerCase().includes(lowerQuery) && node.type === 'file') {
      results.push(node.path)
    }

    if (node.children) {
      for (const child of node.children) {
        traverse(child)
      }
    }
  }

  traverse(node)
  return results
}

/**
 * Get all file paths from tree (flatten).
 *
 * @param node - Root node
 * @returns Array of all file paths
 */
export function flattenFileTree(node: FileNode): string[] {
  const paths: string[] = []

  function traverse(node: FileNode) {
    if (node.type === 'file') {
      paths.push(node.path)
    }

    if (node.children) {
      for (const child of node.children) {
        traverse(child)
      }
    }
  }

  traverse(node)
  return paths
}

/**
 * Count total files in tree.
 *
 * @param node - Root node
 * @returns Total file count
 */
export function countFiles(node: FileNode): number {
  let count = 0

  function traverse(node: FileNode) {
    if (node.type === 'file') {
      count++
    }

    if (node.children) {
      for (const child of node.children) {
        traverse(child)
      }
    }
  }

  traverse(node)
  return count
}

/**
 * Count total directories in tree.
 *
 * @param node - Root node
 * @returns Total directory count
 */
export function countDirectories(node: FileNode): number {
  let count = 0

  function traverse(node: FileNode) {
    if (node.type === 'directory') {
      count++
    }

    if (node.children) {
      for (const child of node.children) {
        traverse(child)
      }
    }
  }

  traverse(node)
  return count - 1 // Exclude root
}

/**
 * Find a node by path.
 *
 * @param root - Root node
 * @param path - Path to find
 * @returns File node or null if not found
 */
export function findNodeByPath(root: FileNode, path: string): FileNode | null {
  function traverse(node: FileNode): FileNode | null {
    if (node.path === path) {
      return node
    }

    if (node.children) {
      for (const child of node.children) {
        const result = traverse(child)
        if (result) return result
      }
    }

    return null
  }

  return traverse(root)
}

/**
 * Get file extension from path.
 *
 * @param path - File path
 * @returns File extension (without dot) or empty string
 */
export function getFileExtension(path: string): string {
  const parts = path.split('.')
  return parts.length > 1 ? parts[parts.length - 1] : ''
}

/**
 * Get language from file extension for syntax highlighting.
 *
 * @param path - File path
 * @returns Language identifier
 */
export function getLanguageFromPath(path: string): string {
  const ext = getFileExtension(path).toLowerCase()

  const languageMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'tsx',
    js: 'javascript',
    jsx: 'jsx',
    py: 'python',
    md: 'markdown',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    html: 'html',
    css: 'css',
    scss: 'scss',
    sh: 'bash',
    rs: 'rust',
    go: 'go',
    java: 'java',
    c: 'c',
    cpp: 'cpp',
    rb: 'ruby',
    php: 'php',
    sql: 'sql',
    xml: 'xml',
  }

  return languageMap[ext] || 'text'
}
