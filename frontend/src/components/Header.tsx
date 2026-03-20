import { Search } from 'lucide-react';

interface Props { onSearch: () => void; onProfile: () => void; apiOnline: boolean; readCount: number; username?: string; }

export function Header({ onSearch, onProfile, apiOnline, readCount, username }: Props) {
  return (
    <header className="relative z-10 flex items-center justify-between bg-white/80 backdrop-blur-sm border-b border-gray-200/80 px-5 h-14 shrink-0">
      <div className="flex items-center gap-4">
        <h1 className="font-serif text-xl text-gray-800 tracking-tight" style={{ letterSpacing: '-0.02em' }}>ResearchViewer</h1>
        <div className="h-5 w-px bg-gray-200" />
        <span className="text-sm text-gray-400 font-light">Topic Explorer</span>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onSearch} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-all active:scale-[0.97]">
          <Search size={15} /><span>Search</span>
          <kbd className="ml-1 px-1.5 py-0.5 text-[10px] font-mono text-gray-400 bg-white border border-gray-200 rounded">⌘K</kbd>
        </button>
        <button onClick={onProfile} className="relative flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100 transition-all">
          <div className="w-7 h-7 rounded-full bg-gray-800 flex items-center justify-center text-xs font-medium text-white">
            {username ? username[0].toUpperCase() : 'U'}
          </div>
          <span className="text-gray-700">Profile</span>
          {readCount > 0 && <span className="px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-600 text-[10px] font-semibold">{readCount}</span>}
        </button>
      </div>
    </header>
  );
}
