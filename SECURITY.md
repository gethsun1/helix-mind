# Security maintenance note

**Assessment date:** 2026-10-01
**Scope:** frontend dependency audit for the submission freeze

## Finding

`npm audit` reports two findings in the frontend dependency tree:

- **Critical: `next@14.2.35`**, a direct runtime dependency. The repository uses the Next.js App Router, middleware, and Vercel deployment. This dependency is part of the public application runtime, so the finding is not development-only. The audit aggregates multiple Next.js advisories, some of which are configuration or feature specific. The repository does not use `next/image`, configure rewrites, or define Server Actions; those facts reduce exposure to advisories limited to those paths but do not establish that every finding is mitigated.
- **High: `postcss@8.4.31`**, pulled transitively by Next.js. It is used in the frontend dependency/build chain. The advisories cover source-map file disclosure and CSS output handling. Exploitability depends on the vulnerable code path and attacker-controlled input; the public deployment does not make this dependency irrelevant.

The September 2026 Next.js security release lists patched lines at Next.js 15.5.27 and 16.3.8. HelixMind is on Next.js 14, so moving to either patched line is a major-version upgrade. `npm audit` currently proposes 16.3.8 as its automatic fix. This is not a low-risk patch within the feature freeze. No dependency or lockfile change was made, and the findings are not resolved. Vercel deployment and the absent `next/image` use do not establish blanket mitigation.

References: [Next.js September 2026 security release](https://nextjs.org/blog/upcoming-nextjs-security-release-september-2026) and [Next.js security advisories](https://github.com/vercel/next.js/security/advisories).

## Submission treatment

This is a known material maintenance risk. Schedule a tested upgrade from Next.js 14 to a currently patched supported release, with compatible dependency/lockfile changes, as the first post-submission maintenance action. Review each applicable advisory against deployed routes and configuration as part of that upgrade. Do not represent the current findings as fixed or fully mitigated.

No production infrastructure, database, or deployed version was changed during this documentation and submission-readiness pass.
