import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, AlertTriangle, ArrowRight, ArrowUpRight, Bot, Check, ClipboardList, Minus, Moon, ShieldAlert, Sun, Wrench,
} from 'lucide-react';
import overviewShot from '../assets/landing/console-overview.jpg';
import remediationShot from '../assets/landing/console-remediation.jpg';
import storeShot from '../assets/landing/store.jpg';
import { Brand } from '../components/Sidebar';
import { DEMO_APP_URL, REPOSITORY_URL, documentUrl } from '../config/links';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useServerStatus } from '../hooks/useServerStatus';

/*
 * Public product page.  Everything stated here describes what the platform
 * does today; the screens are captures of the running console.
 */

const SECTIONS = [
  ['capabilities', 'Capabilities'],
  ['workflow', 'How it works'],
  ['architecture', 'Architecture'],
  ['roles', 'Roles and safeguards'],
  ['demo', 'Demo application'],
  ['documentation', 'Documentation'],
];

const FACTS = [
  ['5', 'alert rules', 'Availability, HTTP 5xx rate, latency, CPU and memory'],
  ['5', 'security rules', 'SEC-001 to SEC-005, with severity and evidence'],
  ['2', 'remediation actions', 'Registered in code. Nothing else can be executed'],
  ['2', 'roles', 'An Operator requests, an Administrator approves'],
];

const CAPABILITIES = [
  {
    icon: Activity,
    name: 'Monitoring',
    text: 'Request rate, error rates, 95th-percentile latency, CPU, memory and uptime of the monitored application and of the API itself, read from Prometheus. A value that cannot be read is shown as unavailable, never estimated.',
    spec: 'Prometheus · scraped every 5 s',
  },
  {
    icon: AlertTriangle,
    name: 'Incidents',
    text: 'A firing alert opens an incident through an authenticated webhook; repeats of the same alert are attached to it instead of opening another. Each incident keeps a timeline and is resolved with evidence when the signal clears.',
    spec: 'Open · Acknowledged · In progress · Resolved · Closed',
  },
  {
    icon: ShieldAlert,
    name: 'Security findings',
    text: 'A cloud configuration file is scanned against five rules: public storage, missing encryption, wildcard IAM permissions, unrestricted inbound access and privileged containers. Each finding carries its severity, the evidence and a recommended fix.',
    spec: 'SEC-001 … SEC-005 · YAML configuration',
  },
  {
    icon: Wrench,
    name: 'Controlled remediation',
    text: 'A fix is requested with a justification, approved or rejected by an Administrator, executed by a separate restricted worker and then verified independently. A failed run stays failed and is reported as such.',
    spec: 'ACTION-001 recover application · ACTION-002 fix public storage',
  },
  {
    icon: ClipboardList,
    name: 'Audit trail',
    text: 'Sign-ins, requests, approvals, executions, refused attempts and demonstration controls are recorded with the actor, the time and the outcome, and can be filtered. Operators see operational events; Administrators see everything.',
    spec: 'Who · what · when · outcome',
  },
  {
    icon: Bot,
    name: 'VigilAI assistant',
    text: 'Answers questions about the platform from its documentation and from the current state it is allowed to read. It explains and points to the right page; it cannot approve or execute anything. Without an AI key it answers from the documentation alone.',
    spec: 'Read-only · Gemini with documentation fallback',
  },
];

const STEPS = [
  ['System', 'Detect', 'Prometheus scrapes the workload every five seconds and evaluates the alert rules.'],
  ['System', 'Open an incident', 'Alertmanager calls an authenticated webhook. The API opens one incident for the alert and attaches repeats to it.'],
  ['Operator', 'Investigate', 'The Operator acknowledges the incident and reads its live metrics and timeline. VigilAI can explain what a signal means.'],
  ['Operator', 'Request a fix', 'The Operator requests a registered action and states why. Nothing is executed yet.'],
  ['Administrator', 'Approve', 'An Administrator approves or rejects the request and dispatches it. An Operator cannot approve.'],
  ['Worker', 'Execute and verify', 'The restricted worker runs the action, with at most three attempts, and the result is checked independently before it counts as a success.'],
  ['System', 'Record', 'When the signal clears the incident is resolved with the evidence attached. Every step above is in the audit trail.'],
];

const PERMISSIONS = [
  ['View monitoring, incidents, findings and remediation', true, true],
  ['Acknowledge, work on and resolve incidents', true, true],
  ['Run security scans', true, true],
  ['Request remediation', true, true],
  ['Use the VigilAI assistant', true, true],
  ['Approve or reject remediation', false, true],
  ['Dispatch execution and retry a failed run', false, true],
  ['Close or reopen incidents', false, true],
  ['Mark a finding as accepted risk', false, true],
  ['Manage users and platform settings', false, true],
  ['Use demonstration controls', false, true],
];

const SAFEGUARDS = [
  ['No self-registration', 'Accounts are created by an Administrator. Sign-in is rate limited and a token stops working at sign-out.'],
  ['Permissions are enforced by the API', 'Hiding a button is never the control. A refused attempt is written to the audit trail.'],
  ['A closed list of actions', 'The worker executes two registered actions. It runs no shell commands and may change one allow-listed file.'],
  ['One public entry point', 'Only the reverse proxy is published. Metrics, alerting and the application’s control endpoints stay on the internal network.'],
  ['Simulated conditions are labelled', 'An incident caused by an injected fault is marked as a demonstration, so it is never mistaken for a real outage.'],
];

const DOCUMENTS = [
  ['Setup guide', 'Start the stack with Docker Compose', 'docs/setup.md'],
  ['User guide', 'Every page of the console, by role', 'docs/user-guide.md'],
  ['Architecture', 'Components, data flow and diagrams', 'docs/architecture.md'],
  ['API reference', 'Endpoints, permissions and examples', 'docs/api.md'],
  ['Security', 'Threat model and the controls in place', 'docs/security.md'],
  ['Verification report', 'What was tested, and what was not', 'docs/verification-report.md'],
];

const ACTOR_TONE = {
  System: 'border-line text-muted',
  Operator: 'border-info/40 text-info',
  Administrator: 'border-warn/50 text-warn',
  Worker: 'border-brand/50 text-brand',
};

/** Which section the reader has reached, for the tab row ('' above the first one). */
function useActiveSection() {
  const [active, setActive] = useState('');
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const line = window.innerHeight * 0.35;
      let current = '';
      for (const [id] of SECTIONS) {
        const node = document.getElementById(id);
        if (node && node.getBoundingClientRect().top <= line) current = id;
      }
      setActive(current);
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);
  return active;
}

function SectionHeading({ label, title, children }) {
  return (
    <header className="mb-9 max-w-2xl">
      <p className="eyebrow text-brand">{label}</p>
      <h2 className="mt-2.5 text-[26px] leading-[1.15] text-content sm:text-[32px]">{title}</h2>
      {children ? <p className="mt-3 text-[15px] leading-6 text-muted">{children}</p> : null}
    </header>
  );
}

/** A capture of the running product in a hairline frame. */
function Screen({ src, alt, caption, className = '' }) {
  return (
    <figure className={className}>
      <div className="overflow-hidden rounded-lg border border-chrome-line bg-chrome shadow-pop">
        <img src={src} alt={alt} width="1440" height="880" loading="lazy" className="block h-auto w-full" />
      </div>
      {caption ? <figcaption className="mt-2.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-muted">{caption}</figcaption> : null}
    </figure>
  );
}

function ServerLine({ status }) {
  const states = {
    checking: ['bg-chrome-muted', 'Checking the demonstration environment'],
    ready: ['bg-[#3ecf8e]', 'Demonstration environment is ready'],
    starting: ['bg-[#f2b544]', 'Demonstration environment is starting. On hosting that sleeps when idle this takes about a minute'],
    unreachable: ['bg-[#ff6363]', 'Demonstration environment is not answering'],
  };
  const [dot, text] = states[status] || states.checking;
  return (
    <p role="status" className="mt-7 flex items-start gap-2.5 font-mono text-[11px] leading-5 tracking-[0.04em] text-chrome-muted">
      <span className={`mt-[7px] h-1.5 w-1.5 shrink-0 rounded-[1px] ${dot}`} aria-hidden="true" />
      {text}
    </p>
  );
}

/** How the components are connected (the Compose stack). */
function ArchitectureDiagram() {
  const box = 'fill-surface stroke-line';
  const name = 'fill-content text-[13px] font-medium';
  const note = 'fill-muted font-mono text-[9.5px] uppercase tracking-[0.08em]';
  const wire = 'stroke-muted/70';
  const label = 'fill-muted font-mono text-[9.5px]';
  const Node = ({ x, y, w = 168, title, sub, accent = false }) => (
    <g>
      <rect x={x} y={y} width={w} height="54" rx="6" className={accent ? 'fill-brand-soft stroke-brand/60' : box} strokeWidth="1" />
      <text x={x + 14} y={y + 24} className={name}>{title}</text>
      <text x={x + 14} y={y + 41} className={note}>{sub}</text>
    </g>
  );
  const Arrow = ({ d, dashed = false }) => (
    <path d={d} fill="none" className={wire} strokeWidth="1.2" strokeDasharray={dashed ? '4 4' : undefined} markerEnd="url(#arrow)" />
  );
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-raised/40">
      <svg viewBox="0 0 1080 430" className="block h-auto w-full min-w-[820px]" role="img" aria-labelledby="architecture-title">
        <title id="architecture-title">
          A browser reaches the reverse proxy, which serves the console, the API and the demonstration application. Prometheus scrapes
          the application, Alertmanager calls the API, the worker takes approved actions from the database, and the API may call the
          external Gemini service.
        </title>
        <defs>
          <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 8 4 0 8z" className="fill-muted" />
          </marker>
        </defs>

        {/* internal network boundary */}
        <rect x="232" y="14" width="654" height="402" rx="10" className="fill-none stroke-line" strokeDasharray="5 5" />
        <text x="248" y="36" className={note}>Internal network</text>

        <Node x={18} y={98} w={150} title="Browser" sub="Operator · Admin" />
        <Node x={252} y={98} w={172} title="Reverse proxy" sub="Caddy · public port" accent />
        <Node x={480} y={34} title="Console" sub="React build" />
        <Node x={480} y={162} title="API" sub="FastAPI · RBAC" />
        <Node x={480} y={246} title="Alertmanager" sub="Notifications" />
        <Node x={480} y={330} title="Prometheus" sub="Metrics · alert rules" />
        <Node x={252} y={330} w={172} title="OrbitCrate" sub="Monitored application" />
        <Node x={700} y={162} title="PostgreSQL" sub="Records · audit trail" />
        <Node x={700} y={290} title="Worker" sub="Runs approved actions" />
        <Node x={906} y={34} w={156} title="Gemini" sub="External · optional" />

        <Arrow d="M168 125H250" />
        <Arrow d="M424 112C452 112 452 61 478 61" />
        <Arrow d="M424 132C452 132 452 189 478 189" />
        <Arrow d="M338 152V328" />
        <text x="346" y="246" className={label}>/orbitcrate/</text>
        <Arrow d="M648 189H698" />
        <Arrow d="M648 176C760 176 800 61 904 61" dashed />
        <text x="806" y="142" className={label}>VigilAI</text>
        <Arrow d="M478 357H426" />
        <text x="452" y="349" textAnchor="middle" className={label}>scrape</text>
        <Arrow d="M564 328V302" />
        <Arrow d="M564 244V218" />
        <text x="572" y="235" className={label}>alert webhook</text>
        <Arrow d="M784 288V218" />
        <text x="792" y="258" className={label}>queue</text>
        <Arrow d="M740 344V397H338V386" dashed />
        <text x="540" y="410" textAnchor="middle" className={label}>recovery endpoint (ACTION-001)</text>
      </svg>
    </div>
  );
}

export default function Landing() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const server = useServerStatus();
  const active = useActiveSection();

  const enter = user
    ? { to: '/', label: 'Open the console' }
    : { to: '/login', label: 'Sign in' };

  return (
    <div className="min-h-screen bg-canvas text-content">
      <a href="#capabilities" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">
        Skip to content
      </a>

      {/* ---------------------------------------------------------------- top */}
      <header className="sticky top-0 z-30 border-b border-chrome-line bg-chrome/95 text-chrome-text backdrop-blur">
        <div className="mx-auto flex h-[56px] max-w-[1240px] items-center justify-between gap-4 px-5 sm:px-8">
          <Link to={user ? '/welcome' : '/'} aria-label="VigilOps" className="rounded-md focus-visible:ring-offset-chrome">
            <Brand onChrome />
          </Link>
          <div className="flex items-center gap-1.5">
            <a
              href={REPOSITORY_URL}
              target="_blank"
              rel="noreferrer"
              className="hidden h-8 items-center gap-1 rounded-md px-2.5 text-[13px] text-chrome-muted transition-colors hover:text-chrome-text focus-visible:ring-offset-chrome sm:inline-flex"
            >
              Source <ArrowUpRight size={13} aria-hidden="true" />
            </a>
            <button
              type="button"
              className="flex h-8 w-8 items-center justify-center rounded-md text-chrome-muted transition-colors hover:bg-white/5 hover:text-chrome-text focus-visible:ring-offset-chrome"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <Link to={enter.to} className="btn-primary ml-1.5 h-8 px-3.5 focus-visible:ring-offset-chrome">
              {enter.label}
            </Link>
          </div>
        </div>
        <nav aria-label="On this page" className="border-t border-chrome-line">
          <div className="mx-auto flex max-w-[1240px] gap-1 overflow-x-auto px-3 sm:px-6">
            {SECTIONS.map(([id, label]) => (
              <a
                key={id}
                href={`#${id}`}
                aria-current={active === id ? 'true' : undefined}
                className={`-mb-px whitespace-nowrap border-b-2 px-2.5 py-2.5 font-mono text-[10.5px] uppercase tracking-[0.1em] transition-colors focus-visible:ring-offset-chrome ${
                  active === id ? 'border-accent text-chrome-text' : 'border-transparent text-chrome-muted hover:text-chrome-text'
                }`}
              >
                {label}
              </a>
            ))}
          </div>
        </nav>
      </header>

      <main>
        {/* -------------------------------------------------------------- hero */}
        <section className="relative overflow-hidden bg-chrome text-chrome-text">
          <div className="dotgrid-chrome pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="relative mx-auto grid max-w-[1240px] gap-12 px-5 pb-16 pt-14 sm:px-8 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-14 lg:pb-24 lg:pt-20">
            <div className="max-w-[560px]">
              <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-accent">Secure cloud operations</p>
              <h1 className="mt-4 text-[38px] font-semibold leading-[1.05] tracking-[-0.03em] sm:text-[50px]">
                Monitoring, incidents and controlled remediation in one console.
              </h1>
              <p className="mt-6 text-[16px] leading-7 text-chrome-muted">
                VigilOps watches a cloud workload through Prometheus, turns real alerts into incidents, scans configuration against
                security rules, and lets an Operator request a fix that an Administrator approves and a restricted worker executes.
                Every step is written to the audit trail.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link to={enter.to} className="btn-primary h-11 px-5 text-[14px] focus-visible:ring-offset-chrome">
                  {enter.label} <ArrowRight size={16} aria-hidden="true" />
                </Link>
                <a
                  href={DEMO_APP_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="btn h-11 border border-chrome-line px-5 text-[14px] text-chrome-text hover:border-chrome-muted hover:bg-white/[0.04] focus-visible:ring-offset-chrome"
                >
                  Open the demo application <ArrowUpRight size={16} aria-hidden="true" />
                </a>
              </div>
              <ServerLine status={server.status} />
            </div>

            <div className="lg:-mr-[22%] lg:pt-1">
              <div className="overflow-hidden rounded-lg border border-chrome-line shadow-pop">
                <img
                  src={overviewShot}
                  alt="The VigilOps overview page: active incidents, open security findings, pending approvals and live metrics of the monitored application."
                  width="1440"
                  height="880"
                  className="block h-auto w-full"
                />
              </div>
              <p className="mt-3 font-mono text-[10.5px] uppercase tracking-[0.12em] text-chrome-muted">
                Overview · live Prometheus telemetry
              </p>
            </div>
          </div>

          <dl className="relative mx-auto grid max-w-[1240px] grid-cols-2 border-t border-chrome-line lg:grid-cols-4">
            {FACTS.map(([figure, name, text], index) => (
              <div
                key={name}
                className={`px-5 py-6 sm:px-8 ${index % 2 ? 'border-l border-chrome-line' : ''} ${index > 1 ? 'border-t border-chrome-line lg:border-t-0' : ''} ${index === 2 ? 'lg:border-l' : ''}`}
              >
                <dt className="flex items-baseline gap-2.5">
                  <span className="text-[30px] font-semibold leading-none tracking-tight tabular-nums">{figure}</span>
                  <span className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-accent">{name}</span>
                </dt>
                <dd className="mt-2 text-[12.5px] leading-5 text-chrome-muted">{text}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* ------------------------------------------------------ capabilities */}
        <section id="capabilities" className="scroll-mt-28 border-b border-line">
          <div className="mx-auto max-w-[1240px] px-5 py-16 sm:px-8 lg:py-24">
            <SectionHeading label="Capabilities" title="Six parts, one closed loop">
              Each part is a page of the console. Together they take a problem from the moment it is measured to the moment its fix is
              verified and recorded.
            </SectionHeading>
            <div className="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
              {CAPABILITIES.map(({ icon: Icon, name, text, spec }, index) => (
                <article key={name} className="flex flex-col bg-surface p-6">
                  <div className="flex items-center justify-between">
                    <Icon size={19} strokeWidth={1.75} className="text-brand" aria-hidden="true" />
                    <span className="font-mono text-[10.5px] text-muted">{String(index + 1).padStart(2, '0')}</span>
                  </div>
                  <h3 className="mt-5 text-[16px] text-content">{name}</h3>
                  <p className="mt-2 text-[13.5px] leading-6 text-muted">{text}</p>
                  <p className="mt-auto pt-5 font-mono text-[10.5px] uppercase leading-4 tracking-[0.08em] text-content/70">{spec}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------- workflow */}
        <section id="workflow" className="scroll-mt-28 border-b border-line bg-surface">
          <div className="mx-auto grid max-w-[1240px] gap-12 px-5 py-16 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16 lg:py-24">
            <div>
              <SectionHeading label="How it works" title="From a signal to a verified fix">
                No step is skipped and no step is automatic that a person should decide. The same sequence applies to an application
                outage and to an insecure configuration.
              </SectionHeading>
              <ol className="border-t border-line">
                {STEPS.map(([actor, name, text], index) => (
                  <li key={name} className="grid grid-cols-[2.25rem_1fr] gap-x-3 border-b border-line py-4">
                    <span className="pt-0.5 font-mono text-[11px] text-muted">{String(index + 1).padStart(2, '0')}</span>
                    <div>
                      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                        <h3 className="text-[14.5px] text-content">{name}</h3>
                        <span className={`badge ${ACTOR_TONE[actor]}`}>{actor}</span>
                      </div>
                      <p className="mt-1.5 text-[13.5px] leading-6 text-muted">{text}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
            <Screen
              className="lg:sticky lg:top-32 lg:self-start"
              src={remediationShot}
              alt="A remediation request in the console: its status steps from pending approval to succeeded, the before and after values, and the audit trail."
              caption="A remediation request · approved, executed and verified"
            />
          </div>
        </section>

        {/* ------------------------------------------------------ architecture */}
        <section id="architecture" className="scroll-mt-28 border-b border-line">
          <div className="mx-auto max-w-[1240px] px-5 py-16 sm:px-8 lg:py-24">
            <SectionHeading label="Architecture" title="Small services with narrow jobs">
              The reference deployment is a Docker Compose stack of seven containers. The API, the worker and the monitored application
              run as unprivileged users on a read-only file system, and only the reverse proxy is published.
            </SectionHeading>
            <ArchitectureDiagram />
            <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-3">
              {[
                ['The API decides, the worker acts', 'The API never executes a fix. It queues an approved request; the worker, which has no inbound port, picks it up.'],
                ['Monitoring is separate from the product', 'Prometheus and Alertmanager measure and notify. The console reads live values from them and stores incidents, not metrics.'],
                ['The AI is optional and read-only', 'VigilAI works from the documentation without an AI key, and with one it still cannot change anything.'],
              ].map(([title, text]) => (
                <div key={title} className="border-t border-line pt-4">
                  <dt className="text-[14px] font-medium text-content">{title}</dt>
                  <dd className="mt-1.5 text-[13.5px] leading-6 text-muted">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        {/* ------------------------------------------------------------- roles */}
        <section id="roles" className="scroll-mt-28 border-b border-line bg-surface">
          <div className="mx-auto max-w-[1240px] px-5 py-16 sm:px-8 lg:py-24">
            <SectionHeading label="Roles and safeguards" title="The person who asks is not the person who approves" />
            <div className="grid gap-12 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] lg:gap-16">
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full min-w-[480px] border-collapse text-left text-[13.5px]">
                  <thead>
                    <tr className="bg-raised/60">
                      <th scope="col" className="border-b border-line px-4 py-3 font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-muted">Permission</th>
                      <th scope="col" className="w-28 border-b border-line px-3 py-3 text-center font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-muted">Operator</th>
                      <th scope="col" className="w-32 border-b border-line px-3 py-3 text-center font-mono text-[10.5px] font-medium uppercase tracking-[0.08em] text-muted">Administrator</th>
                    </tr>
                  </thead>
                  <tbody>
                    {PERMISSIONS.map(([name, operator, admin]) => (
                      <tr key={name} className="border-b border-line/70 last:border-b-0">
                        <th scope="row" className="px-4 py-2.5 font-normal text-content">{name}</th>
                        {[operator, admin].map((allowed, column) => (
                          <td key={column} className="px-3 py-2.5 text-center">
                            {allowed ? (
                              <Check size={15} className="mx-auto text-ok" role="img" aria-label="Allowed" />
                            ) : (
                              <Minus size={15} className="mx-auto text-muted/50" role="img" aria-label="Not allowed" />
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <ul className="border-t border-line">
                {SAFEGUARDS.map(([title, text]) => (
                  <li key={title} className="border-b border-line py-4">
                    <p className="text-[14px] font-medium text-content">{title}</p>
                    <p className="mt-1 text-[13.5px] leading-6 text-muted">{text}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* -------------------------------------------------------------- demo */}
        <section id="demo" className="scroll-mt-28 bg-chrome text-chrome-text">
          <div className="mx-auto grid max-w-[1240px] items-center gap-12 px-5 py-16 sm:px-8 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16 lg:py-24">
            <div>
              <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-accent">Demo application</p>
              <h2 className="mt-2.5 text-[26px] leading-[1.15] sm:text-[32px]">OrbitCrate is the workload being watched</h2>
              <p className="mt-4 text-[15px] leading-7 text-chrome-muted">
                OrbitCrate is a small storefront built for this project: server plans, a price calculator and orders that move from
                received to active. Its orders are not real, but every request is, and those requests are what the console measures.
              </p>
              <ol className="mt-6 space-y-3 text-[14px] leading-6 text-chrome-muted">
                {[
                  'Open OrbitCrate in a second tab and place an order.',
                  'Watch its request rate and latency on the Monitoring page.',
                  'As an Administrator, inject a controlled fault from Settings. The store slows down or fails for real, an alert fires and an incident opens.',
                ].map((text, index) => (
                  <li key={text} className="grid grid-cols-[1.75rem_1fr]">
                    <span className="pt-px font-mono text-[11px] text-accent">{String(index + 1).padStart(2, '0')}</span>
                    {text}
                  </li>
                ))}
              </ol>
              <a
                href={DEMO_APP_URL}
                target="_blank"
                rel="noreferrer"
                className="btn-primary mt-8 h-11 px-5 text-[14px] focus-visible:ring-offset-chrome"
              >
                Open OrbitCrate <ArrowUpRight size={16} aria-hidden="true" />
              </a>
            </div>
            <figure>
              <div className="overflow-hidden rounded-lg border border-chrome-line shadow-pop">
                <img
                  src={storeShot}
                  alt="The OrbitCrate storefront with its store pulse panel, which shows the response time of each request the page makes."
                  width="1440"
                  height="880"
                  loading="lazy"
                  className="block h-auto w-full"
                />
              </div>
              <figcaption className="mt-3 font-mono text-[10.5px] uppercase tracking-[0.12em] text-chrome-muted">
                OrbitCrate · a demonstration store, nothing is provisioned or charged
              </figcaption>
            </figure>
          </div>
        </section>

        {/* ----------------------------------------------------- documentation */}
        <section id="documentation" className="scroll-mt-28">
          <div className="mx-auto max-w-[1240px] px-5 py-16 sm:px-8 lg:py-24">
            <SectionHeading label="Documentation" title="Read how it is built and how it was tested" />
            <ul className="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
              {DOCUMENTS.map(([name, text, path]) => (
                <li key={path} className="bg-surface">
                  <a
                    href={documentUrl(path)}
                    target="_blank"
                    rel="noreferrer"
                    className="group flex h-full items-start justify-between gap-4 p-5 transition-colors hover:bg-raised/60 focus-visible:ring-inset focus-visible:ring-offset-0"
                  >
                    <span>
                      <span className="block text-[14.5px] font-medium text-content">{name}</span>
                      <span className="mt-1 block text-[13px] leading-5 text-muted">{text}</span>
                    </span>
                    <ArrowUpRight size={16} className="mt-0.5 shrink-0 text-muted transition-colors group-hover:text-brand" aria-hidden="true" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      {/* -------------------------------------------------------------- footer */}
      <footer className="border-t border-chrome-line bg-chrome text-chrome-muted">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-x-10 gap-y-5 px-5 py-9 sm:px-8">
          <div className="max-w-xl">
            <Brand onChrome />
            <p className="mt-4 text-[12.5px] leading-5">
              VigilOps is an academic major project. This instance is a demonstration environment: the workload it monitors is a
              demonstration application, and accounts are issued by its Administrator.
            </p>
          </div>
          <div className="flex items-center gap-5 text-[13px]">
            <a href={REPOSITORY_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:text-chrome-text focus-visible:ring-offset-chrome">
              Source code <ArrowUpRight size={13} aria-hidden="true" />
            </a>
            <Link to={enter.to} className="inline-flex items-center gap-1 text-chrome-text hover:text-accent focus-visible:ring-offset-chrome">
              {enter.label} <ArrowRight size={14} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
