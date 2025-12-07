import { useState, useRef, useEffect, ReactNode } from 'react';

interface CollapsibleSectionProps {
  title: string;
  children: ReactNode;
  defaultExpanded?: boolean;
  headerContent?: ReactNode;
}

export function CollapsibleSection({
  title,
  children,
  defaultExpanded = true,
  headerContent,
}: CollapsibleSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [contentHeight, setContentHeight] = useState<number | 'auto'>('auto');
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (contentRef.current) {
      if (isExpanded) {
        // Measure the content height for animation
        const height = contentRef.current.scrollHeight;
        setContentHeight(height);
        // After animation completes, set to auto for dynamic content
        const timer = setTimeout(() => setContentHeight('auto'), 300);
        return () => clearTimeout(timer);
      } else {
        // First set the current height, then animate to 0
        const height = contentRef.current.scrollHeight;
        setContentHeight(height);
        requestAnimationFrame(() => {
          setContentHeight(0);
        });
      }
    }
  }, [isExpanded]);

  return (
    <div className={`collapsible-section ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div
        className="collapsible-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="collapsible-toggle">
          <svg
            className="collapsible-chevron"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="currentColor"
          >
            <path d="M4.5 2L8.5 6L4.5 10" />
          </svg>
          <span className="collapsible-title">{title}</span>
        </div>
        {headerContent && (
          <div className="collapsible-header-content" onClick={(e) => e.stopPropagation()}>
            {headerContent}
          </div>
        )}
      </div>
      <div
        ref={contentRef}
        className="collapsible-content"
        style={{
          height: contentHeight === 'auto' ? 'auto' : `${contentHeight}px`,
          overflow: isExpanded && contentHeight === 'auto' ? 'visible' : 'hidden',
        }}
      >
        <div className="collapsible-inner">
          {children}
        </div>
      </div>
    </div>
  );
}
