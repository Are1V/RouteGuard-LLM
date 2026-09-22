import { PageHeader } from "@/components/shell";

const SETUP_COMMANDS = [
  'pip install -e ".[dev,api]"',
  "routeguard benchmark --config experiments/smoke/smoke.yaml",
  "uvicorn apps.api.main:app --reload",
  "cd apps/web && npm install && npm run dev",
].join("\n");

const PIPELINE_STAGES = [
  "Query analysis",
  "Difficulty",
  "Router",
  "Model",
  "Confidence",
  "Verification",
  "Escalation",
];

export default function AboutPage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="Documentation"
        title="About RouteGuard"
        description="A research framework for studying whether reliability signals can make adaptive LLM routing genuinely useful — not merely more complicated."
      />
      <div className="prose">
        <section>
          <h2>Research question</h2>
          <p>
            Can a lightweight routing system reduce inference cost and latency while maintaining
            answer quality by predicting query difficulty, estimating answer reliability, verifying
            outputs, and escalating uncertain answers?
          </p>
          <div className="flow">
            {PIPELINE_STAGES.map((stage, index) => (
              <span key={stage} style={{ display: "contents" }}>
                <span>{stage}</span>
                {index < PIPELINE_STAGES.length - 1 && <b>→</b>}
              </span>
            ))}
          </div>
        </section>

        <section>
          <h2>What the evidence says</h2>
          <p>
            The reference Qwen3 experiments are a negative result: RouteGuard matched the large
            model&apos;s accuracy but used about 5% more estimated compute and higher latency.
            Small-model answers could not be certified at the target 15% accepted-error risk, so
            frequent escalation removed the hoped-for efficiency gain. These results remain visible
            because they are central to the research question.
          </p>
        </section>

        <section>
          <h2>Methodology</h2>
          <p>
            Experiments use separate train, calibration, and test partitions; parallel multilingual
            examples stay in the same split. Difficulty and routing components fit on training data,
            while confidence calibrators and risk thresholds fit only on calibration data.
            Routing-conditional certification is available because a router changes the distribution
            each model receives.
          </p>
        </section>

        <section>
          <h2>Limitations</h2>
          <ul>
            <li>Estimated TFLOPs, measured latency, energy, and API price are distinct quantities.</li>
            <li>
              A calibrated empirical score is not automatically a formal guarantee; exchangeability
              and selection assumptions matter.
            </li>
            <li>Kazakh confidence ranking was close to chance in the stored runs.</li>
            <li>The simulated backend validates software behavior, not model quality.</li>
            <li>Language comparisons mix datasets unless restricted to parallel subsets.</li>
          </ul>
        </section>

        <section>
          <h2>Reproduce locally</h2>
          <pre>{SETUP_COMMANDS}</pre>
          <p>
            API documentation is available at <code>http://127.0.0.1:8000/docs</code>. The core
            package remains usable without FastAPI or Node.js.
          </p>
        </section>

        <section>
          <h2>Attribution</h2>
          <p>
            RouteGuard-LLM is authored by Mirwais Mohebi and released under the Apache License 2.0.
            Historical runs produced before the repository&apos;s first commit retain their original{" "}
            <code>commit: null</code> provenance.
          </p>
        </section>
      </div>
    </div>
  );
}
