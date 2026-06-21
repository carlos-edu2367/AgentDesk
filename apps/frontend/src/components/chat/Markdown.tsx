import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Renders model output as formatted markdown. GFM enabled (tables, lists,
 * strikethrough). Links open in a new tab. Styling uses simple Tailwind classes
 * so it fits the dark slate theme without a prose plugin dependency.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm text-slate-200 leading-relaxed space-y-2 [&_code]:bg-slate-950 [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_pre]:bg-slate-950 [&_pre]:p-3 [&_pre]:rounded-md [&_pre]:overflow-x-auto [&_a]:text-blue-400 [&_a]:underline [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold [&_table]:w-full [&_th]:text-left [&_th]:border-b [&_th]:border-slate-700 [&_td]:border-b [&_td]:border-slate-800 [&_td]:py-1 [&_blockquote]:border-l-2 [&_blockquote]:border-slate-600 [&_blockquote]:pl-3 [&_blockquote]:text-slate-400">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
