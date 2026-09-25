"use client";

import { useEffect, useState } from "react";

// Every request goes to THIS origin. The browser never learns the service's address and never
// holds its credential; the route handler under /api/agent forwards, having discarded whatever
// identity the client tried to assert.
const API = "/api/agent";

// Mirrors the service's seeded local personas. The picker is a DEV convenience: the server
// validates the selection against its own list, so a hand-crafted value cannot invent a persona.
const PERSONAS = ["analyst", "approver", "auditor", "other-tenant"];

// What happened to the human-review hand-off, in the words the user needs. A result that
// escalated but is not queued must say so rather than read as reviewed.
const REVIEW_ROUTING_TEXT: Record<string, string> = {
  routed: "Sent to the review console.",
  failed: "Could not reach the review console; this result is not queued for review.",
  off: "Review routing is off in this deployment; this result is not queued for review.",
};

function reviewRoutingOf(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body) as { review_routing?: unknown };
    return typeof parsed.review_routing === "string" ? parsed.review_routing : undefined;
  } catch {
    return undefined;
  }
}

// The model classes `POST /v1/validate` accepts, mirroring `ModelClass` in
// src/model_risk_validation/domain/taxonomy.py. An unknown class fails closed on the server.
const MODEL_CLASSES = ["scorecard", "ifrs9_cecl", "irb", "alm", "pricing", "actuarial", "aml_scenario"];

// The optional structured fields of `ValidationRequestModel`, prefilled for a FICTIONAL
// medium-materiality scorecard so the battery computes every metric its pack requires. Delete a
// key to send the service's default: an undeclared dimension fails closed to high, and a metric
// whose sample is absent is reported as a gap.
const DEFAULT_EVIDENCE = {
  dimensions: {
    materiality: "medium",
    complexity: "medium",
    usage: "medium",
    regulatory_exposure: "medium",
  },
  sample: {
    scores: [0.91, 0.84, 0.77, 0.62, 0.55, 0.41, 0.33, 0.27, 0.18, 0.09],
    labels: [1, 1, 1, 0, 1, 0, 0, 0, 0, 0],
    predicted: [0.88, 0.9, 0.86, 0.12, 0.9, 0.1, 0.14, 0.1, 0.12, 0.1],
    outcomes: [1, 1, 1, 0, 1, 0, 0, 0, 0, 0],
    psi_expected: [0.2, 0.3, 0.3, 0.2],
    psi_actual: [0.22, 0.29, 0.28, 0.21],
  },
  observed: { psi: 0.06, auc: 0.81 },
};

interface Evidence {
  dimensions?: Record<string, string>;
  sample?: Record<string, number[]>;
  observed?: Record<string, number>;
}

// The textarea is free text, so it is parsed before anything is sent: a typo is reported here
// rather than posted as a request the service would reject.
function parseEvidence(text: string): Evidence {
  const parsed: unknown = JSON.parse(text);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("the evidence must be a JSON object with dimensions, sample and observed");
  }
  return parsed as Evidence;
}

interface CardSummary {
  name?: string;
  description?: string;
  skills?: { id: string; name: string }[];
}

export default function Home() {
  const [persona, setPersona] = useState(PERSONAS[0]);
  const [modelId, setModelId] = useState("M-SCR-021");
  const [name, setName] = useState("Northwind retail application scorecard (FICTIONAL)");
  const [modelClass, setModelClass] = useState("scorecard");
  const [owner, setOwner] = useState("model.owner@bank.example");
  const [evidenceText, setEvidenceText] = useState(JSON.stringify(DEFAULT_EVIDENCE, null, 2));
  const [result, setResult] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState<CardSummary | null>(null);

  // The service names itself, so this UI carries no hardcoded product name to go stale.
  useEffect(() => {
    let live = true;
    fetch(API + "/.well-known/agent-card.json", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (live) setCard(body as CardSummary | null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    let evidence: Evidence;
    try {
      evidence = parseEvidence(evidenceText);
    } catch (error) {
      setFailed(true);
      setResult("Could not read the evidence JSON: " + String(error));
      return;
    }
    setBusy(true);
    setFailed(false);
    try {
      const response = await fetch(API + "/v1/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dev-Persona": persona },
        body: JSON.stringify({
          model_id: modelId,
          name,
          model_class: modelClass,
          owner,
          dimensions: evidence.dimensions,
          sample: evidence.sample,
          observed: evidence.observed,
        }),
      });
      const body = await response.text();
      setFailed(!response.ok);
      setResult(body);
    } catch (error) {
      setFailed(true);
      setResult(String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>{card?.name ?? "Agent console"}</h1>
      <p className="sub">
        {card?.description ??
          "Validate a model. The tier and battery are deterministic, cited, and routed to a human reviewer when they escalate."}
      </p>

      <form onSubmit={submit}>
        <fieldset>
          <legend>Who you are</legend>
          <label>
            Seeded dev persona (local profile only; the server resolves identity, not this field)
            <select value={persona} onChange={(event) => setPersona(event.target.value)}>
              {PERSONAS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>The model</legend>
          <label>
            Model id
            <input value={modelId} onChange={(event) => setModelId(event.target.value)} />
          </label>
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Model class
            <select value={modelClass} onChange={(event) => setModelClass(event.target.value)}>
              {MODEL_CLASSES.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Owner
            <input value={owner} onChange={(event) => setOwner(event.target.value)} />
          </label>
          <label>
            Evidence (JSON: tiering dimensions, validation sample, monitoring readings)
            <textarea
              rows={18}
              spellCheck={false}
              value={evidenceText}
              onChange={(event) => setEvidenceText(event.target.value)}
            />
          </label>
          <button type="submit" disabled={busy || !modelId || !name || !owner}>
            {busy ? "Working" : "Validate this model"}
          </button>
        </fieldset>
      </form>

      {result && REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""] ? (
        <p className="sub" data-review-routing={reviewRoutingOf(result)}>
          {REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""]}
        </p>
      ) : null}
      {result ? <pre className={failed ? "result error" : "result"}>{result}</pre> : null}

      <footer>
        Synthetic, obviously fictional data only. Identity is resolved server-side and the
        client-asserted actor is discarded; see ui/README.md for the embedding contract.
      </footer>
    </main>
  );
}
