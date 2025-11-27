'use client';

import React, { useState } from 'react';
import { Lightbulb, Loader2 } from 'lucide-react';
import * as Dialog from '@radix-ui/react-dialog';

interface HintButtonProps {
  patternId: string;
  context: string;
  userProgress: string;
  className?: string;
}

export function HintButton({
  patternId,
  context,
  userProgress,
  className = '',
}: HintButtonProps) {
  const [open, setOpen] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [relatedConcepts, setRelatedConcepts] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHint = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/generate/hint', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          patternId,
          context,
          userProgress,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch hint');
      }

      const data = await response.json();
      setHint(data.hint);
      setRelatedConcepts(data.relatedConcepts || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (newOpen && !hint && !loading) {
      fetchHint();
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Trigger asChild>
        <button
          className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[44px] ${className}`}
          aria-label="Get a hint"
        >
          <Lightbulb className="h-4 w-4" aria-hidden="true" />
          Get a Hint
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content
          className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white rounded-lg shadow-xl p-6 w-full max-w-md z-50 focus:outline-none"
          aria-describedby="hint-description"
        >
          <Dialog.Title className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Lightbulb className="h-6 w-6 text-yellow-500" aria-hidden="true" />
            Hint
          </Dialog.Title>

          <div id="hint-description" className="space-y-4">
            {loading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 text-blue-600 animate-spin" aria-hidden="true" />
                <span className="sr-only">Loading hint...</span>
              </div>
            )}

            {error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {hint && !loading && (
              <>
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-gray-700 leading-relaxed">{hint}</p>
                </div>

                {relatedConcepts.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900 mb-2">
                      Related Concepts
                    </h3>
                    <ul className="space-y-1" role="list">
                      {relatedConcepts.map((concept, index) => (
                        <li key={index} className="text-sm text-gray-700 flex items-start gap-2">
                          <span className="text-blue-600 flex-shrink-0">•</span>
                          <span>{concept}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>

          <Dialog.Close asChild>
            <button
              className="mt-6 w-full px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 min-h-[44px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Close hint"
            >
              Got it!
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
