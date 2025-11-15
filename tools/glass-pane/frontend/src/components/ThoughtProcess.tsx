import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface ThoughtProcessProps {
  jobId: string | null;
}

const REPORT_FILES = [
  { name: 'Scout Report', path: '.context-foundry/scout-report.md' },
  { name: 'Architecture', path: '.context-foundry/architecture.md' },
  { name: 'Test Report', path: '.context-foundry/test-report.md' },
];

export default function ThoughtProcess({ jobId }: ThoughtProcessProps) {
  const [selectedReport, setSelectedReport] = useState<string>(REPORT_FILES[0].path);
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (jobId && selectedReport) {
      fetchReport();
    }
  }, [jobId, selectedReport]);

  const fetchReport = async () => {
    if (!selectedReport) return;

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ path: selectedReport });
      const response = await fetch(`/api/files?${params}`);

      if (!response.ok) {
        if (response.status === 404) {
          setContent('Report not yet available');
        } else {
          throw new Error(`Failed to fetch report: ${response.statusText}`);
        }
        return;
      }

      const data = await response.json() as { content: string };
      setContent(data.content);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching report:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg h-[400px] flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <h2 className="text-lg font-semibold text-gray-100 mb-3">Thought Process</h2>

        {/* Report Tabs */}
        <div className="flex gap-2">
          {REPORT_FILES.map(report => (
            <button
              key={report.path}
              onClick={() => setSelectedReport(report.path)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                selectedReport === report.path
                  ? 'bg-cyan-500 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {report.name}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {!jobId && (
          <div className="flex items-center justify-center h-full text-gray-500">
            Select a job to view reports
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

        {jobId && content && !isLoading && !error && (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '');
                  const isInline = !className;

                  return !isInline && match ? (
                    <SyntaxHighlighter
                      language={match[1]}
                      style={vscDarkPlus}
                      PreTag="div"
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold text-gray-100 mb-4 mt-6">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-semibold text-gray-200 mb-3 mt-5">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-semibold text-gray-300 mb-2 mt-4">{children}</h3>
                ),
                p: ({ children }) => (
                  <p className="text-gray-300 mb-4 leading-relaxed">{children}</p>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc list-inside text-gray-300 mb-4 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside text-gray-300 mb-4 space-y-1">{children}</ol>
                ),
                li: ({ children }) => (
                  <li className="text-gray-300">{children}</li>
                ),
                a: ({ children, href }) => (
                  <a href={href} className="text-cyan-400 hover:text-cyan-300 underline" target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-cyan-500 pl-4 italic text-gray-400 my-4">
                    {children}
                  </blockquote>
                ),
                table: ({ children }) => (
                  <div className="overflow-x-auto mb-4">
                    <table className="min-w-full border border-gray-700">{children}</table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-gray-800">{children}</thead>
                ),
                th: ({ children }) => (
                  <th className="border border-gray-700 px-4 py-2 text-left text-gray-200">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="border border-gray-700 px-4 py-2 text-gray-300">{children}</td>
                ),
              }}
            >
              {content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
