import { useEffect } from 'react';
import { X, Database, Github, BookOpen } from 'lucide-react';

interface Props {
  onClose: () => void;
}

export function AboutPanel({ onClose }: Props) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50">
      <div className="fixed inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up" onClick={e => e.stopPropagation()}>
          <div className="px-6 py-5 border-b border-gray-100">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-800">About ResearchViewer</h2>
              <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400">
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="px-6 py-5 space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <BookOpen size={16} className="text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">What is this?</h3>
              </div>
              <p className="text-sm text-gray-600 leading-relaxed">
                ResearchViewer is an interactive explorer for arXiv research papers. Navigate through research domains, topics, and microtopics to discover papers and track your reading journey.
              </p>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <Database size={16} className="text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">Data Source</h3>
              </div>
              <p className="text-sm text-gray-600 leading-relaxed mb-2">
                The dataset includes arXiv papers with hierarchical topic labels and citation networks.
              </p>
              <a
                href="https://huggingface.co/datasets/ShayManor/Labeled-arXiv"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                <span>View on Hugging Face</span>
                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>

            <div>
              <div className="flex items-center gap-2 mb-2">
                <Github size={16} className="text-gray-400" />
                <h3 className="text-sm font-semibold text-gray-700">Open Source</h3>
              </div>
              <p className="text-sm text-gray-600 leading-relaxed">
                Built with React, Flask, and DuckDB. The codebase is available for exploration and contributions.
              </p>
            </div>
          </div>

          <div className="px-6 py-4 bg-gray-50 border-t border-gray-100">
            <p className="text-xs text-gray-400 text-center">
              Press <kbd className="px-1.5 py-0.5 bg-white border border-gray-200 rounded text-gray-600 font-mono">ESC</kbd> to close
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
