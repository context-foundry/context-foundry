import { useEffect, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { MarkdownUpdateData } from '../types/events';

interface MarkdownFile {
  name: string;
  path: string;
  size: number;
  modified: number;
  type: string;
}

interface MarkdownViewerProps {
  jobId: string | null;
  onMarkdownUpdate?: (data: MarkdownUpdateData) => void;
}

export default function MarkdownViewer({ jobId, onMarkdownUpdate }: MarkdownViewerProps) {
  const [files, setFiles] = useState<MarkdownFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch list of markdown files
  const fetchFiles = useCallback(async () => {
    if (!jobId) {
      setFiles([]);
      return;
    }

    try {
      const response = await fetch(`/api/artifacts/${jobId}/markdown`);
      if (!response.ok) {
        throw new Error(`Failed to fetch markdown files: ${response.statusText}`);
      }

      const data = await response.json() as { files: MarkdownFile[] };
      setFiles(data.files);

      // Auto-select first file if nothing is selected
      if (data.files.length > 0 && !selectedFile) {
        setSelectedFile(data.files[0].name);
      }
    } catch (err) {
      console.error('Error fetching markdown files:', err);
      setFiles([]);
    }
  }, [jobId, selectedFile]);

  // Fetch content of selected file
  const fetchContent = useCallback(async () => {
    if (!jobId || !selectedFile) {
      setContent('');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/artifacts/${jobId}/markdown/${selectedFile}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch file: ${response.statusText}`);
      }

      const text = await response.text();
      setContent(text);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching markdown content:', err);
    } finally {
      setIsLoading(false);
    }
  }, [jobId, selectedFile]);

  // Initial fetch
  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  // Fetch content when selection changes
  useEffect(() => {
    fetchContent();
  }, [fetchContent]);

  // Handle markdown update events from SSE
  useEffect(() => {
    if (onMarkdownUpdate) {
      // Parent component will call handleMarkdownUpdate
    }
  }, [onMarkdownUpdate]);

  const handleMarkdownUpdate = useCallback((data: MarkdownUpdateData) => {
    // Refresh file list to include new file
    fetchFiles();

    // If the updated file is currently selected, refresh its content
    if (selectedFile === data.name) {
      fetchContent();
    }
  }, [fetchFiles, fetchContent, selectedFile]);

  // Expose handler to parent
  useEffect(() => {
    if (onMarkdownUpdate) {
      // This is a hack to pass the handler up
      (window as any).__markdownViewerHandler = handleMarkdownUpdate;
    }
  }, [handleMarkdownUpdate, onMarkdownUpdate]);

  const getFileIcon = (type: string): string => {
    switch (type) {
      case 'scout':
        return '🔍';
      case 'architect':
        return '📐';
      case 'builder':
        return '🔨';
      case 'test':
        return '🧪';
      case 'summary':
        return '📊';
      default:
        return '📄';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Group files by type
  const groupedFiles = files.reduce((acc, file) => {
    const type = file.type;
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(file);
    return acc;
  }, {} as Record<string, typeof files>);

  // Type order and labels
  const typeOrder = ['scout', 'architect', 'builder', 'test', 'summary', 'other'];
  const typeLabels: Record<string, string> = {
    scout: 'Scout Reports',
    architect: 'Architecture',
    builder: 'Builder',
    test: 'Test Reports',
    summary: 'Summaries',
    other: 'Other',
  };

  return (
    <div className="h-full flex">
      {/* File List Sidebar */}
      <div className="w-64 border-r border-gray-800 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h2 className="text-sm font-semibold text-gray-100">Build Artifacts</h2>
          </div>
          {files.length > 0 && (
            <div className="text-xs text-gray-500">{files.length} file{files.length !== 1 ? 's' : ''}</div>
          )}
        </div>

        {/* File List */}
        <div className="flex-1 overflow-y-auto">
          {!jobId && (
            <div className="p-4 text-sm text-gray-500 text-center">
              Select a job
            </div>
          )}

          {jobId && files.length === 0 && !isLoading && (
            <div className="p-4 text-sm text-gray-500 text-center">
              No artifacts found
            </div>
          )}

          {isLoading && (
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-500" />
            </div>
          )}

          {files.length > 0 && (
            <div className="py-2">
              {typeOrder.map((type) => {
                const typeFiles = groupedFiles[type];
                if (!typeFiles || typeFiles.length === 0) return null;

                return (
                  <div key={type} className="mb-3">
                    <div className="px-3 py-1 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      {typeLabels[type]}
                    </div>
                    {typeFiles.map((file) => (
                      <button
                        key={file.name}
                        onClick={() => setSelectedFile(file.name)}
                        className={`w-full text-left px-3 py-2 transition-colors ${
                          selectedFile === file.name
                            ? 'bg-cyan-500/20 border-l-2 border-cyan-500 text-cyan-400'
                            : 'hover:bg-gray-800 border-l-2 border-transparent text-gray-300'
                        }`}
                      >
                        <div className="flex items-start gap-2">
                          <span className="text-base flex-shrink-0 mt-0.5">{getFileIcon(file.type)}</span>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-medium truncate">{file.name.replace('.md', '')}</div>
                            <div className="text-xs opacity-75">{formatFileSize(file.size)}</div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 flex flex-col">
        {/* Content Header */}
        {selectedFile && (
          <div className="p-3 border-b border-gray-800 bg-gray-800/50">
            <div className="text-sm font-medium text-gray-300 truncate">{selectedFile}</div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {!selectedFile && (
            <div className="flex items-center justify-center h-full text-gray-500">
              {files.length > 0 ? 'Select a file to view' : 'No artifacts available'}
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

          {content && !isLoading && !error && (
            <div className="prose prose-invert prose-cyan max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  // Customize rendering
                  h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mb-4 text-cyan-400" {...props} />,
                  h2: ({ node, ...props }) => <h2 className="text-xl font-bold mb-3 text-cyan-400" {...props} />,
                  h3: ({ node, ...props }) => <h3 className="text-lg font-bold mb-2 text-cyan-400" {...props} />,
                  p: ({ node, ...props }) => <p className="mb-4 text-gray-300 leading-relaxed" {...props} />,
                  ul: ({ node, ...props }) => <ul className="list-disc list-inside mb-4 text-gray-300 space-y-1" {...props} />,
                  ol: ({ node, ...props }) => <ol className="list-decimal list-inside mb-4 text-gray-300 space-y-1" {...props} />,
                  code: ({ node, inline, className, children, ...props }: any) => {
                    return inline ? (
                      <code className="bg-gray-800 px-1.5 py-0.5 rounded text-cyan-400 text-sm" {...props}>
                        {children}
                      </code>
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                  pre: ({ node, ...props }) => (
                    <pre className="bg-gray-800 p-4 rounded-lg overflow-x-auto mb-4 border border-gray-700" {...props} />
                  ),
                  blockquote: ({ node, ...props }) => (
                    <blockquote className="border-l-4 border-cyan-500 pl-4 italic text-gray-400 mb-4" {...props} />
                  ),
                  table: ({ node, ...props }) => (
                    <div className="overflow-x-auto mb-4">
                      <table className="min-w-full border border-gray-700" {...props} />
                    </div>
                  ),
                  th: ({ node, ...props }) => (
                    <th className="bg-gray-800 border border-gray-700 px-4 py-2 text-left font-semibold text-cyan-400" {...props} />
                  ),
                  td: ({ node, ...props }) => (
                    <td className="border border-gray-700 px-4 py-2 text-gray-300" {...props} />
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
