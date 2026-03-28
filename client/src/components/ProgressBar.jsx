export default function ProgressBar({ value }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-white/5">
      <div
        className="h-full rounded-full bg-gradient-to-r from-signal-500 via-cyan-300 to-signal-300 transition-all"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}
