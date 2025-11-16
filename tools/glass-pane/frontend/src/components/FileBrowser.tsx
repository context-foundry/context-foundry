import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FileNode } from '../types/job';

interface FileBrowserProps {
  visibleNodes: FileNode[];
  toggleDirectory: (path: string) => void;
  collapseAll: () => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  jobId?: string | null;
}

export default function FileBrowser({
  visibleNodes,
  toggleDirectory,
  collapseAll,
  searchQuery,
  setSearchQuery,
  jobId,
}: FileBrowserProps) {
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  const handleNodeClick = async (node: FileNode) => {
    if (node.type === 'directory') {
      toggleDirectory(node.path);
    } else {
      setSelectedPath(node.path);
      await fetchFile(node.path);
    }
  };

  const fetchFile = async (filePath: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ path: filePath });
      if (jobId) {
        params.append('job_id', jobId);
      }
      const response = await fetch(`/api/files?${params}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch file: ${response.statusText}`);
      }

      const data = await response.json() as { content: string };
      setContent(data.content);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching file:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const getIndentLevel = (path: string): number => {
    return path.split('/').length - 1;
  };

  const getLanguage = (path: string): string => {
    const ext = path.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'tsx':
      case 'jsx':
        return 'tsx';
      case 'ts':
        return 'typescript';
      case 'js':
        return 'javascript';
      case 'py':
        return 'python';
      case 'json':
        return 'json';
      case 'md':
        return 'markdown';
      case 'css':
        return 'css';
      case 'scss':
        return 'scss';
      case 'html':
        return 'html';
      case 'yaml':
      case 'yml':
        return 'yaml';
      case 'sh':
        return 'bash';
      default:
        return 'text';
    }
  };

  const handleCopy = async () => {
    if (!content) return;

    try {
      await navigator.clipboard.writeText(content);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="h-full w-full flex">
      {/* File Tree Sidebar */}
      <div className="w-64 min-w-[256px] border-r border-gray-800 flex flex-col flex-shrink-0">
        {/* Header */}
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <h2 className="text-sm font-semibold text-gray-100">Project Files</h2>
          </div>
          {visibleNodes.length > 0 && (
            <div className="text-xs text-gray-500">{visibleNodes.length} item{visibleNodes.length !== 1 ? 's' : ''}</div>
          )}
        </div>

        {/* Search */}
        <div className="p-4 border-b border-gray-800">
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
          <button
            onClick={collapseAll}
            className="mt-2 text-xs text-gray-400 hover:text-gray-300 transition-colors"
          >
            Collapse All
          </button>
        </div>

        {/* File Tree */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden py-2">
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
                >
                  <button
                    onClick={() => handleNodeClick(node)}
                    className={`w-full text-left px-3 py-2 transition-colors ${
                      isSelected
                        ? 'bg-cyan-500/20 border-l-2 border-cyan-500 text-cyan-400'
                        : 'hover:bg-gray-800 border-l-2 border-transparent text-gray-300'
                    }`}
                    style={{ paddingLeft: `${12 + indentLevel * 16}px` }}
                  >
                    <div className="flex items-center gap-2">
                      {/* Icon */}
                      {node.type === 'directory' ? (
                        <span className="text-base flex-shrink-0">
                          {node.expanded ? '📂' : '📁'}
                        </span>
                      ) : (
                        <span className="text-base flex-shrink-0">
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
                    </div>
                  </button>
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

      {/* Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Content Header */}
        {selectedPath && (
          <div className="p-3 border-b border-gray-800 bg-gray-800/50 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              <div className="text-sm font-medium text-gray-300 truncate">{selectedPath}</div>
            </div>

            <button
              onClick={handleCopy}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors text-sm ml-4"
            >
              {isCopied ? (
                <>
                  <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-green-400">Copied!</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  <span>Copy</span>
                </>
              )}
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto min-w-0">
          {!selectedPath && (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select a file to preview
            </div>
          )}

          {isLoading && (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500" />
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-full">
              <div className="text-red-400 text-sm">{error}</div>
            </div>
          )}

          {selectedPath && content && !isLoading && !error && (
            <SyntaxHighlighter
              language={getLanguage(selectedPath)}
              style={vscDarkPlus}
              showLineNumbers
              customStyle={{
                margin: 0,
                padding: '1rem',
                background: 'transparent',
                fontSize: '0.875rem',
              }}
              lineNumberStyle={{
                minWidth: '3em',
                paddingRight: '1em',
                color: '#6b7280',
                userSelect: 'none',
              }}
            >
              {content}
            </SyntaxHighlighter>
          )}
        </div>
      </div>
    </div>
  );
}
