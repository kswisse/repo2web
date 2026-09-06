export function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">R2W</span>
          </div>
          <span className="font-semibold text-gray-900">Repo2Web</span>
        </div>
        <nav className="text-sm text-gray-500">
          Phase 0
        </nav>
      </div>
    </header>
  );
}
