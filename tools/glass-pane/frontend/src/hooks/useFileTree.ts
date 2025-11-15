import { useState, useCallback, useMemo } from 'react';
import { FileNode } from '../types/job';

export function useFileTree(initialFiles: string[] = []) {
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['/']));
  const [searchQuery, setSearchQuery] = useState('');
  const [files, setFiles] = useState<string[]>(initialFiles);

  const toggleDirectory = useCallback((path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const collapseAll = useCallback(() => {
    setExpandedDirs(new Set(['/']));
  }, []);

  const expandAll = useCallback((tree: FileNode[]) => {
    const allDirs = new Set<string>(['/']);

    const collectDirs = (nodes: FileNode[], parentPath = '') => {
      nodes.forEach(node => {
        if (node.type === 'directory') {
          const fullPath = parentPath ? `${parentPath}/${node.name}` : node.name;
          allDirs.add(fullPath);
          if (node.children) {
            collectDirs(node.children, fullPath);
          }
        }
      });
    };

    collectDirs(tree);
    setExpandedDirs(allDirs);
  }, []);

  const addFile = useCallback((filePath: string) => {
    setFiles(prev => {
      if (prev.includes(filePath)) return prev;
      return [...prev, filePath].sort();
    });
  }, []);

  const fileTree = useMemo(() => {
    const root: FileNode[] = [];
    const filteredFiles = searchQuery
      ? files.filter(f => f.toLowerCase().includes(searchQuery.toLowerCase()))
      : files;

    filteredFiles.forEach(filePath => {
      const parts = filePath.split('/').filter(Boolean);
      let currentLevel = root;

      parts.forEach((part, index) => {
        const isFile = index === parts.length - 1;
        const existingNode = currentLevel.find(node => node.name === part);

        if (existingNode) {
          if (!isFile && existingNode.children) {
            currentLevel = existingNode.children;
          }
        } else {
          const newNode: FileNode = {
            path: parts.slice(0, index + 1).join('/'),
            name: part,
            type: isFile ? 'file' : 'directory',
            expanded: expandedDirs.has(parts.slice(0, index + 1).join('/')),
            created_at: new Date().toISOString(),
          };

          if (!isFile) {
            newNode.children = [];
            currentLevel.push(newNode);
            currentLevel = newNode.children;
          } else {
            currentLevel.push(newNode);
          }
        }
      });
    });

    return root;
  }, [files, searchQuery, expandedDirs]);

  const visibleNodes = useMemo(() => {
    const visible: FileNode[] = [];

    const traverse = (nodes: FileNode[]) => {
      nodes.forEach(node => {
        visible.push(node);
        if (node.type === 'directory' && node.children && expandedDirs.has(node.path)) {
          traverse(node.children);
        }
      });
    };

    traverse(fileTree);
    return visible;
  }, [fileTree, expandedDirs]);

  return {
    fileTree,
    visibleNodes,
    expandedDirs,
    toggleDirectory,
    collapseAll,
    expandAll,
    searchQuery,
    setSearchQuery,
    addFile,
    setFiles,
  };
}
