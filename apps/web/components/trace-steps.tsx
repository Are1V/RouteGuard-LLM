import { buildSteps } from "@/lib/trace";
import type { InferenceResult } from "@/lib/types";

export function TraceSteps({ result }: { result: InferenceResult }) {
  const steps = buildSteps(result);
  return (
    <ol className="trace-line" aria-label="Pipeline path taken by this request">
      {steps.map((step, index) => (
        <li
          key={`${step.kind}-${index}`}
          className={`trace-step ${step.kind}`}
          style={{ "--i": index } as React.CSSProperties}
        >
          <span className="trace-step-label">{step.label}</span>
          <span className="trace-step-detail">{step.detail}</span>
        </li>
      ))}
    </ol>
  );
}
