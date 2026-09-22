import { PageHeader } from "@/components/shell";

const SETUP_COMMANDS = [
  'pip install -e ".[dev,api]"',
  "cd apps/web && npm install && cd ../..",
  "./scripts/run_web.sh",
].join("\n");

export default function AboutPage() {
  return (
    <div className="page">
      <PageHeader
        eyebrow="About"
        title="Built for reliable routing"
        description="A practical control layer for multi-model LLM applications."
      />

      <div className="prose">
        <section>
          <h2>What it does</h2>
          <p>
            RouteGuard analyzes each request, selects a model, checks the response, and escalates
            when confidence is low. Every decision is recorded with latency, token, and cost data.
          </p>
        </section>

        <section>
          <h2>Use it locally</h2>
          <pre>{SETUP_COMMANDS}</pre>
          <p>
            Open <code>http://127.0.0.1:3000</code>. API documentation is available at{" "}
            <code>http://127.0.0.1:8000/docs</code>.
          </p>
        </section>

        <section>
          <h2>Important notes</h2>
          <ul>
            <li>Demo mode validates the workflow; it does not represent model quality.</li>
            <li>Real performance depends on the selected models and configuration.</li>
            <li>The optional code verifier is not a security sandbox.</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
