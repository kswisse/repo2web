import type { AnalysisResult } from "@/lib/types";

interface Props {
  result: AnalysisResult;
  onDeploy: () => void;
}

export function AnalysisResults({ result, onDeploy }: Props) {
  return (
    <div className="mt-8 bg-white border border-gray-200 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Analysis Results</h2>
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <span className="text-sm text-gray-500">Framework</span>
          <p className="font-medium text-gray-900">{result.framework || "Not detected"}</p>
        </div>
        <div>
          <span className="text-sm text-gray-500">Confidence</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 rounded-full"
                style={{ width: `${result.confidence * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-700">
              {Math.round(result.confidence * 100)}%
            </span>
          </div>
        </div>
      </div>
      {result.warnings.length > 0 && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-700">
          {result.warnings.map((w, i) => (
            <p key={i}>{w}</p>
          ))}
        </div>
      )}
      <button
        onClick={onDeploy}
        className="px-6 py-2 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 transition-colors"
      >
        Deploy
      </button>
    </div>
  );
}
