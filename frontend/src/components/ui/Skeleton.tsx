interface SkeletonProps {
  className?: string;
  lines?: number;
}

export function Skeleton({ className = 'h-4 w-full', lines = 1 }: SkeletonProps) {
  return (
    <div aria-hidden="true" className="flex flex-col gap-2">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className={`animate-pulse rounded bg-slate-200 ${className}`}
        />
      ))}
    </div>
  );
}
