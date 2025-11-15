import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileNode } from '../types/job';

interface FileTreeProps {
  onFileSelect: (filePath: string) => void;
  visibleNodes: FileNode[];
  toggleDirectory: (path: string) => void;
  collapseAll: () => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export default function FileTree({
  onFileSelect,
  visibleNodes,
  toggleDirectory,
  collapseAll,
  searchQuery,
  setSearchQuery,
}: FileTreeProps) {

  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const handleNodeClick = (node: FileNode) => {
    if (node.type === 'directory') {
      toggleDirectory(node.path);
    } else {
      setSelectedPath(node.path);
      onFileSelect(node.path);
    }
  };

  const getIndentLevel = (path: string): number => {
    return path.split('/').length - 1;
  };

  return (
    <div className="p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-end mb-4">
        <button
          onClick={collapseAll}
          className="text-xs text-gray-400 hover:text-gray-300 transition-colors"
        >
          Collapse All
        </button>
      </div>

      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search files..."
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 pl-10 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
          />
          <svg
            className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* File Tree */}
      <div className="flex-1 overflow-y-auto space-y-1">
        <AnimatePresence>
          {visibleNodes.map((node) => {
            const indentLevel = getIndentLevel(node.path);
            const isSelected = selectedPath === node.path;

            return (
              <motion.div
                key={node.path}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                style={{ paddingLeft: `${indentLevel * 16}px` }}
                className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-cyan-500/20 text-cyan-400'
                    : 'hover:bg-gray-800 text-gray-300'
                }`}
                onClick={() => handleNodeClick(node)}
              >
                {/* Icon */}
                {node.type === 'directory' ? (
                  <span className="text-sm">
                    {node.expanded ? '📂' : '📁'}
                  </span>
                ) : (
                  <span className="text-sm">
                    {node.name.endsWith('.tsx') || node.name.endsWith('.jsx') ? '⚛️' :
                     node.name.endsWith('.ts') || node.name.endsWith('.js') ? '📜' :
                     node.name.endsWith('.py') ? '🐍' :
                     node.name.endsWith('.md') ? '📝' :
                     node.name.endsWith('.json') ? '📋' :
                     node.name.endsWith('.css') || node.name.endsWith('.scss') ? '🎨' :
                     '📄'}
                  </span>
                )}

                {/* Name */}
                <span className="text-sm truncate">{node.name}</span>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {visibleNodes.length === 0 && (
          <div className="text-center py-8 text-gray-500 text-sm">
            {searchQuery ? 'No files match your search' : 'No files yet'}
          </div>
        )}
      </div>
    </div>
  );
}
