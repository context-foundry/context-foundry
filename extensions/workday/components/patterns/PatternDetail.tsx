'use client';

import React from 'react';
import { CheckCircle2, XCircle, Lightbulb, Link2, Tag } from 'lucide-react';
import { Pattern } from '@/types/pattern';

interface PatternDetailProps {
  pattern: Pattern;
}

export function PatternDetail({ pattern }: PatternDetailProps) {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-gray-200 pb-6">
        <div className="flex flex-wrap gap-2 mb-4">
          <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium">
            {pattern.category}
          </span>
          {pattern.module && (
            <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-medium">
              {pattern.module}
            </span>
          )}
          {pattern.difficulty && (
            <span className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm font-medium capitalize">
              {pattern.difficulty}
            </span>
          )}
        </div>

        <h1 className="text-3xl font-bold text-gray-900 mb-4">{pattern.name}</h1>
        <p className="text-lg text-gray-700 leading-relaxed">{pattern.description}</p>
      </div>

      {/* Applies To */}
      {pattern.applies_to && pattern.applies_to.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Tag className="h-5 w-5 text-gray-600" aria-hidden="true" />
            Applies To
          </h2>
          <div className="flex flex-wrap gap-2">
            {pattern.applies_to.map((item, index) => (
              <span
                key={index}
                className="px-3 py-1 bg-gray-100 text-gray-700 rounded-md text-sm"
              >
                {item}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Best Practices */}
      <section>
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-green-600" aria-hidden="true" />
          Best Practices
        </h2>
        <ul className="space-y-3" role="list">
          {pattern.best_practices.map((practice, index) => (
            <li key={index} className="flex gap-3 text-gray-700">
              <span className="flex-shrink-0 mt-1">
                <CheckCircle2 className="h-5 w-5 text-green-600" aria-hidden="true" />
              </span>
              <span className="leading-relaxed">{practice}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Anti-Patterns */}
      {pattern.anti_patterns && pattern.anti_patterns.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" aria-hidden="true" />
            Anti-Patterns to Avoid
          </h2>
          <ul className="space-y-3" role="list">
            {pattern.anti_patterns.map((antiPattern, index) => (
              <li key={index} className="flex gap-3 text-gray-700">
                <span className="flex-shrink-0 mt-1">
                  <XCircle className="h-5 w-5 text-red-600" aria-hidden="true" />
                </span>
                <span className="leading-relaxed">{antiPattern}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Examples */}
      {pattern.examples && pattern.examples.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-yellow-600" aria-hidden="true" />
            Examples
          </h2>
          <div className="space-y-4">
            {pattern.examples.map((example, index) => (
              <div
                key={index}
                className="bg-gray-50 border border-gray-200 rounded-lg p-4"
              >
                <p className="text-gray-700 leading-relaxed">{example}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Related Patterns */}
      {pattern.related_patterns && pattern.related_patterns.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Link2 className="h-5 w-5 text-blue-600" aria-hidden="true" />
            Related Patterns
          </h2>
          <div className="flex flex-wrap gap-2">
            {pattern.related_patterns.map((relatedPattern, index) => (
              <span
                key={index}
                className="px-3 py-2 bg-blue-50 text-blue-700 rounded-md text-sm border border-blue-200"
              >
                {relatedPattern}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Tags */}
      {pattern.tags && pattern.tags.length > 0 && (
        <section>
          <h2 className="text-xl font-semibold text-gray-900 mb-3">Tags</h2>
          <div className="flex flex-wrap gap-2">
            {pattern.tags.map((tag, index) => (
              <span
                key={index}
                className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs"
              >
                #{tag}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
