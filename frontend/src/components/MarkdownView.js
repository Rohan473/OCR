import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';

export const MarkdownView = ({ children, className = '' }) => {
  return (
    <div className={`markdown-body text-sm leading-relaxed ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mt-6 mb-3" {...props} />,
          h2: ({ node, ...props }) => <h2 className="text-xl font-semibold mt-5 mb-2" {...props} />,
          h3: ({ node, ...props }) => <h3 className="text-lg font-semibold mt-4 mb-2" {...props} />,
          p: ({ node, ...props }) => <p className="my-3 leading-relaxed" {...props} />,
          ul: ({ node, ...props }) => <ul className="list-disc ml-6 my-3 space-y-1" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal ml-6 my-3 space-y-1" {...props} />,
          li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
          code: ({ node, inline, ...props }) =>
            inline
              ? <code className="bg-muted px-1 py-0.5 rounded text-sm font-mono" {...props} />
              : <code className="block bg-muted p-3 rounded text-sm font-mono overflow-x-auto" {...props} />,
          pre: ({ node, ...props }) => <pre className="bg-muted rounded my-3 overflow-x-auto" {...props} />,
          blockquote: ({ node, ...props }) => (
            <blockquote className="border-l-4 border-orange-400 pl-4 italic text-muted-foreground my-3" {...props} />
          ),
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-3">
              <table className="min-w-full border-collapse border border-border" {...props} />
            </div>
          ),
          th: ({ node, ...props }) => <th className="border border-border px-3 py-1.5 bg-muted text-left font-semibold" {...props} />,
          td: ({ node, ...props }) => <td className="border border-border px-3 py-1.5" {...props} />,
          hr: () => <hr className="my-6 border-border" />,
        }}
      >
        {children || ''}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownView;
