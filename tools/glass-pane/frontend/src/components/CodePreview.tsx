import { useEffect, useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodePreviewProps {
  filePath: string | null;
}

export default function CodePreview({ filePath }: CodePreviewProps) {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (!filePath) {
      setContent('');
      return;
    }

    fetchFile();
  }, [filePath]);

  const fetchFile = async () => {
    if (!filePath) return;

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ path: filePath });
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
    <div className="bg-gray-900 border border-gray-800 rounded-lg h-[500px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
          <h2 className="text-lg font-semibold text-gray-100">Code Preview</h2>
        </div>

        {filePath && (
          <button
            onClick={handleCopy}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors text-sm"
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
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {!filePath && (
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

        {filePath && content && !isLoading && !error && (
          <SyntaxHighlighter
            language={getLanguage(filePath)}
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

      {/* Footer */}
      {filePath && (
        <div className="p-2 border-t border-gray-800 bg-gray-800/50">
          <div className="text-xs text-gray-400 truncate">{filePath}</div>
        </div>
      )}
    </div>
  );
}
